from src.services.extraction import extract_from_transcript
from src.schemas import TranscriptRequest, Message


def test_extract_ignores_without_openai_key(monkeypatch):
    # With LLM-only pipeline and no key, expect no memories
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    req = TranscriptRequest(
        user_id="u1",
        history=[Message(role="user", content="I love sci-fi books."),],
    )
    result = extract_from_transcript(req)
    assert result.memories == []


def test_ignores_non_user_messages():
    req = TranscriptRequest(
        user_id="u2",
        history=[Message(role="assistant", content="You said you like coffee.")],
    )
    result = extract_from_transcript(req)
    assert result.memories == []


def test_no_memories_when_history_empty():
    req = TranscriptRequest(user_id="u3", history=[])
    result = extract_from_transcript(req)
    assert result.memories == []


