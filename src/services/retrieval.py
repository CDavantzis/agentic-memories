from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import hashlib
import json

from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.config import get_embedding_model_name
from src.services.extraction import _generate_embedding


COLLECTION_NAME = "memories"


def _embedding_dim_from_model(model: str) -> int:
	name = (model or "").lower()
	if "text-embedding-3-large" in name:
		return 3072
	if "text-embedding-3-small" in name:
		return 1536
	# Default to 3072 if unknown
	return 3072


def _standard_collection_name() -> str:
	model = get_embedding_model_name()
	dim = _embedding_dim_from_model(model)
	return f"{COLLECTION_NAME}_{dim}"


def _get_collection() -> Any:
	client = get_chroma_client()
	if client is None:
		raise RuntimeError("Chroma client not available")
	return client.get_collection(_standard_collection_name())  # type: ignore[attr-defined]


def _hash_query(query: str) -> str:
	return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _keyword_score(query: str, doc: str) -> float:
	q_tokens = set(query.lower().split())
	d_tokens = set(doc.lower().split())
	if not q_tokens or not d_tokens:
		return 0.0
	return len(q_tokens & d_tokens) / len(q_tokens)


def _hybrid_score(semantic: float, keyword: float) -> float:
	return 0.8 * semantic + 0.2 * keyword


def search_memories(
	user_id: str,
	query: str,
	filters: Optional[Dict[str, Any]] = None,
	limit: int = 10,
	offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
	filters = filters or {}
	redis = get_redis_client()
	use_cache = redis is not None and (filters.get("layer") == "short-term")

	cache_key = None
	if use_cache:
		ns = redis.get(f"mem:ns:{user_id}") or "0"
		cache_key = f"mem:srch:{user_id}:{_hash_query(query)}:v{ns}"
		cached = redis.get(cache_key)
		if cached:
			data = json.loads(cached)
			return data["results"], data.get("total", len(data["results"]))

	collection = _get_collection()

	# Basic metadata filter
	where: Dict[str, Any] = {"user_id": user_id}
	if "layer" in filters and filters["layer"]:
		where["layer"] = filters["layer"]
	if "type" in filters and filters["type"]:
		where["type"] = filters["type"]
	# tags filter (best-effort; stored as JSON string)
	if "tags" in filters and filters["tags"]:
		where["tags"] = {"$contains": json.dumps(filters["tags"])[:256]}

	# Build query embedding locally
	emb = _generate_embedding(query) or []

	# Semantic query
	semantic_results = collection.query(  # type: ignore[attr-defined]
		query_embeddings=[emb], n_results=limit + offset, where=where
	)

	ids: List[str] = semantic_results.get("ids", [[]])[0]
	docs: List[str] = semantic_results.get("documents", [[]])[0]
	scores: List[float] = semantic_results.get("distances", [[]])[0]
	metas: List[Dict[str, Any]] = semantic_results.get("metadatas", [[]])[0]

	items: List[Dict[str, Any]] = []
	for i, mem_id in enumerate(ids):
		if i >= len(docs) or i >= len(metas) or i >= len(scores):
			continue
		semantic_sim = 1.0 - float(scores[i]) if scores else 0.0
		k_score = _keyword_score(query, docs[i])
		final = _hybrid_score(semantic_sim, k_score)
		item = {
			"id": mem_id,
			"content": docs[i],
			"score": final,
			"metadata": metas[i],
		}
		items.append(item)

	# Sort by final score and paginate
	items.sort(key=lambda x: x["score"], reverse=True)
	total = len(items)
	page = items[offset : offset + limit]

	# Cache short-term
	if use_cache and cache_key and redis is not None:
		redis.setex(cache_key, 180, json.dumps({"results": page, "total": total}))

	return page, total


