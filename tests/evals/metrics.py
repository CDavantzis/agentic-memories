from __future__ import annotations

from typing import Dict, List, Tuple


def canonicalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def score_predictions(gold_items: List[str], pred_items: List[str]) -> Dict[str, float]:
    gold = {canonicalize(x) for x in gold_items}
    pred = {canonicalize(x) for x in pred_items}
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


