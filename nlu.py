from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

_MONTH_MAP = {m: i for i, m in enumerate(
    ["january","february","march","april","may","june",
     "july","august","september","october","november","december"], start=1)}

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
    t = _norm(text)
    if image_uri:
        return "IMAGE_ASSESS", 0.8
    if re.search(r"(how to|what steps|procedure).*(mow|maintain|repair)", t):
        return "SOP_QUERY", 0.8
    if re.search(r"(which|list|show).*(cost|overdue|park|parks|mow|labor)", t):
        return "DATA_QUERY", 0.75
    return "DATA_QUERY", 0.6

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