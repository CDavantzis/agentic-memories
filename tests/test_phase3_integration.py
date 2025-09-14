from datetime import datetime, timezone
from fastapi.testclient import TestClient
from src.models import Memory


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

    # Patch the symbol used by the route handler
    monkeypatch.setattr(app_mod, "extract_from_transcript", _stub_extract)

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


