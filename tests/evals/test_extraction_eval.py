import json
from pathlib import Path

import os
import pytest

from src.schemas import TranscriptRequest, Message
from src.services.extraction import extract_from_transcript
from tests.evals.metrics import score_predictions
from src import config as cfg


FIXTURE = Path(__file__).parent / "fixtures" / "sample_extraction.jsonl"


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture missing")
def test_extraction_eval_smoke(monkeypatch):
    # Allow running without OpenAI by heuristic-only mode if no key
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("Requires OPENAI_API_KEY for LLM-only extraction")

    gold_texts = []
    pred_texts = []

    with FIXTURE.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            req = TranscriptRequest(
                user_id=row["user_id"],
                history=[Message(**m) for m in row["history"]],
            )
            result = extract_from_transcript(req)
            for g in row["gold"]:
                gold_texts.append(g["content"]) 
            for m in result.memories:
                pred_texts.append(m.content)

    metrics = score_predictions(gold_texts, pred_texts)
    # Smoke check: ensure recall reasonably high in aggressive mode
    assert metrics["recall"] >= 0.5


