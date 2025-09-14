from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.models import Memory
from tests.fixtures.chroma_mock import create_mock_v2_chroma_client


def test_store_and_retrieve_roundtrip(monkeypatch):
    # Stub extraction to avoid external OpenAI dependency
    from src import app as app_mod

    def _stub_extract(body):
        mem = Memory(
            user_id=body.user_id,
            content="User loves sci-fi books.",
            layer="semantic",
            type="explicit",
            embedding=[0.1]*16,
            timestamp=datetime.now(timezone.utc),
            confidence=0.9,
            ttl=None,
            usage_count=0,
            relevance_score=0.5,
            metadata={"tags": ["behavior"]},
        )
        from src.services.extraction import ExtractionResult
        return ExtractionResult(memories=[mem], summary="stub")

    # Mock storage and retrieval services
    def mock_upsert_memories(user_id: str, memories):
        return [f"mem_{i}" for i in range(len(memories))]

    def mock_search_memories(user_id: str, query: str, filters=None, limit=10, offset=0):
        mock_results = [
            {
                "id": "mem_0",
                "content": "User loves sci-fi books.",
                "layer": "semantic",
                "type": "explicit",
                "score": 0.9,
                "metadata": {"tags": ["behavior"]}
            }
        ]
        return mock_results, 1

    # Mock OpenAI API key check
    def mock_get_openai_api_key():
        return "sk-test-key-12345"
    
    # Patch the symbols used by the route handlers
    monkeypatch.setattr(app_mod, "extract_from_transcript", _stub_extract)
    monkeypatch.setattr(app_mod, "upsert_memories", mock_upsert_memories)
    monkeypatch.setattr(app_mod, "search_memories", mock_search_memories)
    monkeypatch.setattr(app_mod, "get_openai_api_key", mock_get_openai_api_key)

    # Build client AFTER patching
    client = TestClient(app_mod.app)
    
    # Store transcript
    payload = {
        "user_id": "u_phase3",
        "history": [{"role": "user", "content": "I love sci-fi books."}],
    }
    resp = client.post("/v1/store", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["memories_created"] >= 1
    assert len(data["ids"]) == data["memories_created"]

    # Retrieve
    r = client.get(
        "/v1/retrieve",
        params={"query": "sci-fi", "limit": 5, "user_id": "u_phase3"},
    )
    assert r.status_code == 200
    rd = r.json()
    assert isinstance(rd.get("results"), list)
    assert rd.get("pagination", {}).get("limit") == 5


