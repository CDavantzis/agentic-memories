from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.app import app
from src.services.prompts import EXTRACTION_PROMPT
from tests.fixtures.chroma_mock import create_mock_v2_chroma_client


client = TestClient(app)



def test_store_stub(monkeypatch):
	# With LLM-only pipeline and no key, expect zero memories
	monkeypatch.delenv("OPENAI_API_KEY", raising=False)
	payload = {
		"user_id": "user-123",
		"history": [{"role": "user", "content": "I love sci-fi books."}],
	}
	resp = client.post("/v1/store", json=payload)
	assert resp.status_code == 400
	data = resp.json()
	assert data["detail"] == "OPENAI_API_KEY is required"
	assert "ids" not in data


def test_retrieve_stub():
	# Mock the entire search_memories function
	from src.services.retrieval import search_memories
	
	def mock_search_memories(user_id: str, query: str, filters=None, limit=10, offset=0):
		# Return mock results
		mock_results = [
			{
				"id": "mem_1",
				"content": "User loves sci-fi books.",
				"layer": "semantic",
				"type": "explicit",
				"score": 0.9,
				"metadata": {"tags": ["behavior"]}
			}
		]
		return mock_results, 1
	
	with patch('src.app.search_memories', side_effect=mock_search_memories):
		resp = client.get("/v1/retrieve", params={"query": "sci-fi", "limit": 5})
		assert resp.status_code == 200
		data = resp.json()
		assert "results" in data and isinstance(data["results"], list)
		assert "pagination" in data
		assert len(data["results"]) == 1
		assert data["results"][0]["content"] == "User loves sci-fi books."


def test_health_full_structure():
	resp = client.get("/health/full")
	assert resp.status_code == 200
	data = resp.json()
	assert "status" in data
	assert "checks" in data and isinstance(data["checks"], dict)


def test_extraction_prompt_normalization_rules():
	"""Test that the extraction prompt includes comprehensive normalization rules."""
	assert "CONTENT NORMALIZATION RULES" in EXTRACTION_PROMPT
	assert "Content MUST begin with the literal prefix \"User \"" in EXTRACTION_PROMPT
	assert "I love X\" → \"User loves X" in EXTRACTION_PROMPT
	assert "I like X\" → \"User likes X" in EXTRACTION_PROMPT
	assert "I prefer X\" → \"User prefers X" in EXTRACTION_PROMPT
	assert "is running 3 times a week\" → \"runs 3 times a week" in EXTRACTION_PROMPT
	assert "Preserve explicit temporal phrases" in EXTRACTION_PROMPT
	assert "Ensure content ends with a period" in EXTRACTION_PROMPT
	assert "Examples of proper normalization" in EXTRACTION_PROMPT

