from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException

from src.schemas import (
	ForgetRequest,
	MaintenanceRequest,
	MaintenanceResponse,
	RetrieveItem,
	RetrieveResponse,
	StoreResponse,
	StoreMemoryItem,
	TranscriptRequest,
	StructuredRetrieveRequest,
	StructuredRetrieveResponse,
)
from src.dependencies.chroma import get_chroma_client
from src.dependencies.redis_client import get_redis_client
from src.config import get_openai_api_key, get_chroma_host, get_chroma_port
import httpx
from src.services.extraction import extract_from_transcript
from src.services.storage import upsert_memories
from src.services.retrieval import search_memories
from src.services.extract_utils import _call_llm_json

app = FastAPI(title="Agentic Memories API", version="0.1.0")


@app.on_event("startup")
def require_openai_key() -> None:
	api_key = get_openai_api_key()
	if api_key is None or (isinstance(api_key, str) and api_key.strip() == ""):
		raise RuntimeError("OPENAI_API_KEY is required for server startup.")


@app.get("/health")
def health() -> dict:
	return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/health/full")
def health_full() -> dict:
	checks = {}

	# Env check
	required_envs = ["OPENAI_API_KEY"]
	openai_key = get_openai_api_key()
	missing_envs = [k for k in required_envs if (openai_key is None or openai_key.strip() == "")]
	checks["env"] = {"required": required_envs, "missing": missing_envs}

	# ChromaDB check (active heartbeat)
	chroma_ok = False
	chroma_error: Optional[str] = None
	try:
		host = get_chroma_host()
		port = get_chroma_port()
		url = f"http://{host}:{port}/api/v2/heartbeat"
		with httpx.Client(timeout=2.0) as client:
			resp = client.get(url)
			chroma_ok = resp.status_code == 200
	except Exception as exc:  # pragma: no cover
		chroma_error = str(exc)
	checks["chroma"] = {"ok": chroma_ok, "error": chroma_error}

	# Redis check (optional)
	redis_ok = None
	redis_error: Optional[str] = None
	try:
		redis_client = get_redis_client()
		if redis_client is None:
			redis_ok = None  # not configured
		else:
			redis_ok = bool(redis_client.ping())
	except Exception as exc:  # pragma: no cover
		redis_ok = False
		redis_error = str(exc)
	checks["redis"] = {"ok": redis_ok, "error": redis_error}

	overall_ok = chroma_ok and (redis_ok is None or redis_ok) and len(missing_envs) == 0
	return {
		"status": "ok" if overall_ok else "degraded",
		"time": datetime.now(timezone.utc).isoformat(),
		"checks": checks,
	}


@app.post("/v1/store", response_model=StoreResponse)
def store_transcript(body: TranscriptRequest) -> StoreResponse:
	# Guard: enforce OpenAI key presence (LLM-only extraction)
	api_key = get_openai_api_key()
	if api_key is None or (isinstance(api_key, str) and api_key.strip() == ""):
		raise HTTPException(status_code=400, detail="OPENAI_API_KEY is required")
	# Phase 2: Extract memories only (no persistence yet)
	result = extract_from_transcript(body)
	# Phase 3: Persist to ChromaDB
	ids = upsert_memories(body.user_id, result.memories)
	# Bump Redis namespace for this user to invalidate short-term caches
	try:
		redis = get_redis_client()
		if redis is not None:
			redis.incr(f"mem:ns:{body.user_id}")
	except Exception:
		pass
	items = [
		StoreMemoryItem(
			id=ids[i],
			content=m.content,
			layer=m.layer,
			type=m.type,
			confidence=m.confidence,
			ttl=m.ttl,
			timestamp=m.timestamp,
			metadata=m.metadata,
		)
		for i, m in enumerate(result.memories)
	]
	return StoreResponse(memories_created=len(ids), ids=ids, summary=result.summary, memories=items)


@app.get("/v1/retrieve", response_model=RetrieveResponse)
def retrieve(
	query: str = Query(...),
	user_id: Optional[str] = Query(default=""),
	layer: Optional[str] = Query(default=None),
	type: Optional[str] = Query(default=None),
	limit: int = Query(default=10, ge=1, le=50),
	offset: int = Query(default=0, ge=0),
) -> RetrieveResponse:
	filters: dict = {}
	if layer:
		filters["layer"] = layer
	if type:
		filters["type"] = type
	results, total = search_memories(user_id=user_id or "", query=query, filters=filters, limit=limit, offset=offset)  # Phase 4 will enforce auth-derived user_id
	items = [
		RetrieveItem(
			id=r["id"],
			content=r["content"],
			layer=r["metadata"].get("layer", "semantic"),
			type=r["metadata"].get("type", "explicit"),
			score=float(r.get("score", 0.0)),
			metadata=r.get("metadata", {}),
		)
		for r in results
	]
	return RetrieveResponse(results=items, pagination={"limit": limit, "offset": offset, "total": total})


# Advanced structured retrieval endpoint
@app.post("/v1/retrieve/structured", response_model=StructuredRetrieveResponse)
def retrieve_structured(body: StructuredRetrieveRequest) -> StructuredRetrieveResponse:
	api_key = get_openai_api_key()
	if api_key is None or (isinstance(api_key, str) and api_key.strip() == ""):
		raise HTTPException(status_code=400, detail="OPENAI_API_KEY is required")
	if not body.query or body.query.strip() == "":
		raise HTTPException(status_code=400, detail="query is required for structured retrieval")

	# Pull a wider set of candidates
	results, _ = search_memories(user_id=body.user_id, query=body.query, filters={}, limit=max(20, body.limit), offset=0)

	# Map candidates into a lightweight payload
	candidates = [
		{
			"id": r["id"],
			"content": r["content"],
			"metadata": r.get("metadata", {}),
			"score": float(r.get("score", 0.0)),
		}
		for r in results
	]

	SYSTEM_PROMPT = (
		"You are a retrieval organizer for a personal memory system.\n"
		"Given a user query and a list of candidate memories, select and categorize the most relevant memories into these buckets: \n"
		"- emotions\n- behaviors\n- personal\n- professional\n- habits\n- skills_tools\n- projects\n- relationships\n- learning_journal\n- other\n"
		"Return strict JSON with keys exactly as above. For each key, return an array of memory ids from the candidates (do not invent ids).\n"
		"Favor precision but include relevant context. Do not exceed 10 items per category."
	)
	payload = {"query": body.query, "candidates": candidates}
	resp = _call_llm_json(SYSTEM_PROMPT, payload)
	if not isinstance(resp, dict):
		resp = {}

	# Helper to map ids -> RetrieveItem
	id_to_item = {r["id"]: r for r in results}
	def build_items(id_list: List[str]) -> List[RetrieveItem]:
		items: List[RetrieveItem] = []
		for _id in id_list or []:
			src = id_to_item.get(_id)
			if not src:
				continue
			items.append(
				RetrieveItem(
					id=src["id"],
					content=src["content"],
					layer=src["metadata"].get("layer", "semantic"),
					type=src["metadata"].get("type", "explicit"),
					score=float(src.get("score", 0.0)),
					metadata=src.get("metadata", {}),
				)
			)
		return items

	return StructuredRetrieveResponse(
		emotions=build_items(list(resp.get("emotions", []))),
		behaviors=build_items(list(resp.get("behaviors", []))),
		personal=build_items(list(resp.get("personal", []))),
		professional=build_items(list(resp.get("professional", []))),
		habits=build_items(list(resp.get("habits", []))),
		skills_tools=build_items(list(resp.get("skills_tools", []))),
		projects=build_items(list(resp.get("projects", []))),
		relationships=build_items(list(resp.get("relationships", []))),
		learning_journal=build_items(list(resp.get("learning_journal", []))),
		other=build_items(list(resp.get("other", []))),
	)


@app.post("/v1/forget")
def forget(body: ForgetRequest) -> dict:
	return {"jobs_enqueued": ["ttl_cleanup", "promotion"], "dry_run": body.dry_run}


@app.post("/v1/maintenance", response_model=MaintenanceResponse)
def maintenance(body: MaintenanceRequest) -> MaintenanceResponse:
	return MaintenanceResponse(jobs_started=body.jobs or ["compaction"], status="running")
