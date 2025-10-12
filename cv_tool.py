from __future__ import annotations
from typing import Optional
from rag import RAG

def cv_assess_rag(image_uri: str, topic_hint: Optional[str] = None):
    mock = {
        "condition": "fair",
        "score": 0.62,
        "labels": ["mowing_lines_visible", "edge_wear"],
        "explanations": ["Mowing pattern detected; slight edge wear near boundaries."],
        "low_confidence": False,
    }
    hits = RAG.retrieve(topic_hint or "turf mowing inspection wear disease standard safety", k=3)
    return {"cv": mock, "support": hits}