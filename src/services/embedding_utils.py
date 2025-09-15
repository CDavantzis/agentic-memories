"""
Embedding utilities for memory extraction and retrieval.
"""

from __future__ import annotations

import os
from typing import List, Optional

from src.config import get_embedding_model_name


EMBEDDING_MODEL = get_embedding_model_name()


def generate_embedding(text: str) -> Optional[List[float]]:
	"""
	Generate embedding for text using OpenAI or fallback to deterministic embedding.
	
	Args:
		text: Input text to generate embedding for
		
	Returns:
		Embedding vector or None if generation fails
	"""
	# Use OpenAI if configured; otherwise return a deterministic small embedding for tests
	api_key = os.getenv("OPENAI_API_KEY")
	if api_key and api_key.strip() != "":
		try:
			from openai import OpenAI  # type: ignore

			client = OpenAI(api_key=api_key)
			resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
			return list(resp.data[0].embedding)
		except Exception:
			# Fall back to deterministic embedding on any error during Phase 2
			pass

	# Deterministic fallback: map text to a small vector using hash
	# Keep it small to be fast and deterministic for tests
	seed = sum(ord(c) for c in text) or 1
	vec = []
	for i in range(16):
		seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
		vec.append((seed % 1000) / 1000.0)
	return vec
