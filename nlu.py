from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except Exception:
    SentenceTransformer = None
    np = None

_MONTH_MAP = {m: i for i, m in enumerate(
    ["january","february","march","april","may","june",
     "july","august","september","october","november","december"], start=1)}

# intent examples for embedding-based classifier
_INTENT_EXAMPLES = {
    "DATA_QUERY": [
        "Which park had the highest mowing cost in March 2025?",
        "Show total labor cost by park for 2024",
        "Which parks are overdue for mowing?"
    ],
    "SOP_QUERY": [
        "What are the mowing steps and safety requirements?",
        "How to perform standard mowing procedures?",
        "What equipment and safety gear are required for mowing?"
    ],
    "IMAGE_ASSESS": [
        "Inspect this turf for disease and wear",
        "Is this patch a disease or normal wear?",
        "Assess turf condition from photo"
    ]
}

_intent_model = None
_intent_centroids: Optional[Dict[str, np.ndarray]] = None

def _init_intent_model():
    """Lazy-load sentence-transformers model and compute per-intent centroids."""
    global _intent_model, _intent_centroids
    if _intent_model is not None:
        return
    if SentenceTransformer is None or np is None:
        _intent_model = None
        _intent_centroids = None
        return
    try:
        _intent_model = SentenceTransformer("all-MiniLM-L6-v2")
        centroids: Dict[str, np.ndarray] = {}
        for intent, examples in _INTENT_EXAMPLES.items():
            embs = _intent_model.encode(examples, convert_to_numpy=True, show_progress_bar=False)
            centroid = embs.mean(axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            centroids[intent] = centroid
        _intent_centroids = centroids
    except Exception:
        _intent_model = None
        _intent_centroids = None

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _normalize_month_year(t: str) -> tuple[Optional[int], Optional[int]]:
    t = _norm(t).replace(",", " ")
    month, year = None, None

    m_ym = re.search(r"\b(20\d{2})-(\d{1,2})\b", t)
    if m_ym:
        year  = int(m_ym.group(1))
        month = int(m_ym.group(2))
        if 1 <= month <= 12:
            return month, year
        month = None

    for name, idx in _MONTH_MAP.items():
        if re.search(rf"\b{name}\b", t):
            month = idx
            break

    m_y = re.search(r"\b(20\d{2})\b", t)
    if m_y:
        year = int(m_y.group(1))
    return month, year

def classify_intent(text: str, image_uri: Optional[str]) -> (str, float):
    """
    Embedding-based intent detection using all-MiniLM-L6-v2.
    - If model unavailable, fall back to the original regex rules.
    - Returns (intent_label, confidence 0.0-1.0).
    """
    t = _norm(text)
    if image_uri:
        return "IMAGE_ASSESS", 0.95

    _init_intent_model()
    if _intent_model is None or _intent_centroids is None:
        # fallback to rule-based classifier
        if re.search(r"(how to|what steps|procedure).*(mow|maintain|repair)", t):
            return "SOP_QUERY", 0.8
        if re.search(r"(which|list|show).*(cost|overdue|park|parks|mow|labor)", t):
            return "DATA_QUERY", 0.75
        return "DATA_QUERY", 0.6

    # embed query and compute cosine similarity against intent centroids
    q_emb = _intent_model.encode([t], convert_to_numpy=True, show_progress_bar=False)[0]
    q_norm = np.linalg.norm(q_emb)
    if q_norm > 0:
        q_emb = q_emb / q_norm

    best_intent = "DATA_QUERY"
    best_sim = -1.0
    for intent, centroid in _intent_centroids.items():
        sim = float(np.dot(q_emb, centroid))
        if sim > best_sim:
            best_sim = sim
            best_intent = intent

    # convert cosine (-1..1) to confidence (0..1)
    conf = float((best_sim + 1.0) / 2.0)
    return best_intent, round(conf, 2)

def extract_slots(text: str, image_uri: Optional[str]) -> Dict[str, Any]:
    t = _norm(text)
    month, year = _normalize_month_year(t)
    park = None
    m = re.search(r"(in|at)\s+([a-z][a-z\s\-]+park)", t)
    if m:
        park = m.group(2).title()
    return {"image_uri": image_uri, "month": month, "year": year, "park_name": park}

def build_route_plan(intent: str, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    if intent == "SOP_QUERY":
        plan.append({"tool": "kb_retrieve",
                     "args": {"query": "mowing standard safety equipment frequency lane kilometer pricing", "top_k": 5}})
        plan.append({"tool": "sop_extract",
                     "args": {"schema": ["steps", "materials", "tools", "safety"]}})
    elif intent == "IMAGE_ASSESS":
        plan.append({"tool": "cv_assess_rag",
                     "args": {"image_uri": slots.get("image_uri"),
                              "topic_hint": "turf wear disease inspection guidelines"}})
    else:
        plan.append({"tool": "sql_query_rag",
                     "args": {"template": "labor_cost_month_top1",
                              "params": {"month": slots.get("month"), "year": slots.get("year")},
                              "qctx": "mowing labor cost month frequency pricing lane kilometer unit rate standard"}})
    return plan

def nlu_parse(text: str, image_uri: Optional[str] = None) -> Dict[str, Any]:
    intent, conf = classify_intent(text, image_uri)
    slots = extract_slots(text, image_uri)
    plan  = build_route_plan(intent, slots)
    clar = []
    if intent == "DATA_QUERY" and (not slots.get("month") or not slots.get("year")):
        clar.append("Which month/year?")
    return {"intent": intent, "confidence": round(conf, 2),
            "slots": slots, "route_plan": plan, "clarifications": clar}