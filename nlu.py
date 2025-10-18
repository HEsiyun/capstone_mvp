# nlu.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

from sentence_transformers import SentenceTransformer, util

# ---------- MiniLM encoder ----------
_ENCODER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ---------- Few-shot prototypes ----------
INTENT_PROTOTYPES = {
    "RAG+SQL_tool": [
        "Which park had the highest total mowing labor cost in March 2025?",
        "Show me the most expensive park for mowing in April",
        "What was the top mowing cost by location last month?",
    ],
    "RAG": [
        # Mowing procedures
        "What are the mowing steps and safety requirements?",
        "How do I maintain the turf properly?",
        "What equipment do I need for mowing?",
        "Tell me the standard operating procedures for mowing",
        
        # Field dimensions (NEW)
        "What are the dimensions for U15 soccer?",
        "Show me baseball field requirements for U13",
        "What's the pitching distance for female softball U17?",
        "What are the standard dimensions for U10 soccer field?",
        "Tell me the requirements for softball U15",
        "What size should a U18 baseball diamond be?",
    ],
    "SQL_tool": [
        "How did total mowing costs trend from April to June 2025?",
        "Show mowing cost trend from January to March",
        "What's the cost trend for Cambridge Park over time?",
        "Compare mowing costs across all parks in March 2025",
        "Show me all parks ranked by mowing cost",
        "What's the cost breakdown by park?",
        "When was the last mowing at Cambridge Park?",
        "Show me the most recent mowing date for each park",
        "Which parks haven't been mowed recently?",
        "Show total mowing costs breakdown by park in March 2025",
        "What's the cost breakdown for Garden Park?",
    ],
    "RAG+CV_tool": [
        "Here is a picture. What's the estimated labour cost to repair the turf?",
        "Here is a picture. Help me plan the layout of this sports field effectively.",
        "Check this image and tell me if the grass needs mowing",
        "Analyze this field photo and estimate repair costs",
        "What's wrong with the turf in this image?",
    ],
    "CV_tool": [
        "Check this image and assess turf condition.",
        "Analyze this photo of the field",
        "What do you see in this image?",
        "Assess the condition shown in the picture",
    ],
}

# Pre-encode prototypes
_PROT_TEXTS: List[str] = []
_PROT_LABELS: List[str] = []
for label, samples in INTENT_PROTOTYPES.items():
    for s in samples:
        _PROT_TEXTS.append(s)
        _PROT_LABELS.append(label)
_PROT_EMB = _ENCODER.encode(_PROT_TEXTS, normalize_embeddings=True)

# ---------- month/year & park parsing ----------
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january","february","march","april","may","june",
            "july","august","september","october","november","december"
        ],
        start=1,
    )
}
_MONTH_ABBR = {k[:3]: v for k, v in _MONTHS.items()}


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _parse_month_year(text: str) -> Tuple[Optional[int], Optional[int]]:
    t = _norm(text).replace(",", " ")
    # YYYY-MM
    m = re.search(r"\b(20\d{2})-(\d{1,2})\b", t)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return mo, y

    # full month
    for name, idx in _MONTHS.items():
        if re.search(rf"\b{name}\b", t):
            mo = idx
            y = None
            yy = re.search(r"\b(20\d{2})\b", t)
            if yy:
                y = int(yy.group(1))
            return mo, y

    # abbr month (Apr, Jun...)
    for abbr, idx in _MONTH_ABBR.items():
        if re.search(rf"\b{abbr}\b", t):
            mo = idx
            y = None
            yy = re.search(r"\b(20\d{2})\b", t)
            if yy:
                y = int(yy.group(1))
            return mo, y

    # only year
    yy = re.search(r"\b(20\d{2})\b", t)
    if yy:
        return None, int(yy.group(1))

    return None, None


def _parse_month_range(text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Parse month range or single month
    Returns: (start_month, end_month, year)
    
    Supports:
    - "from April to June 2025" -> (4, 6, 2025)
    - "in June 2025" -> (6, 6, 2025)  # single month
    - "trend in March" -> (3, 3, None)
    """
    t = _norm(text)
    
    # Pattern 1: explicit range "from X to Y"
    m = re.search(
        r"(?:from|between)\s+([a-zA-Z]+)\s+(?:to|and)\s+([a-zA-Z]+)\s*(20\d{2})?",
        t,
    )
    if m:
        m1, m2 = m.group(1).lower(), m.group(2).lower()
        y = int(m.group(3)) if m.group(3) else None

        def _to_month(s: str) -> Optional[int]:
            if s in _MONTHS: return _MONTHS[s]
            s3 = s[:3]
            return _MONTH_ABBR.get(s3)
        return _to_month(m1), _to_month(m2), y
    
    # Pattern 2: single month "in June 2025" or "trend in March"
    for name, idx in _MONTHS.items():
        if re.search(rf"\bin\s+{name}\b", t):
            yy = re.search(r"\b(20\d{2})\b", t)
            y = int(yy.group(1)) if yy else None
            return idx, idx, y
    
    for abbr, idx in _MONTH_ABBR.items():
        if re.search(rf"\bin\s+{abbr}\b", t):
            yy = re.search(r"\b(20\d{2})\b", t)
            y = int(yy.group(1)) if yy else None
            return idx, idx, y
    
    return None, None, None


def _parse_park(text: str) -> Optional[str]:
    """Enhanced park name extraction"""
    t = _norm(text)
    
    # Pattern 1: "in XXX Park" / "at XXX Park"
    m = re.search(r"(?:in|at|for)\s+([a-z][a-z\s\-\&]+(?:park|pk))\b", t)
    if m:
        park_raw = m.group(1).strip()
        park_clean = park_raw.replace(" park", "").replace(" pk", "").strip()
        return park_clean.title()
    
    # Pattern 2: known park names
    known_parks = [
        "alice town", "cambridge", "garden", "grandview", 
        "mcgill", "mcspadden", "mosaic creek", "cariboo",
        "john hendry", "hastings", "new brighton"
    ]
    for park in known_parks:
        if park in t:
            return park.title()
    
    return None


def _detect_domain(text: str) -> str:
    """Detect domain: mowing / field_standards / generic"""
    t = _norm(text)
    
    # Mowing domain
    if any(k in t for k in ["mowing", "mow", "turf", "grass", "lawn"]):
        return "mowing"
    
    # Field standards domain
    if any(k in t for k in ["soccer", "baseball", "softball", "cricket", "football", "rugby", "lacrosse", "field", "dimensions", "pitching", "u10", "u11", "u12", "u13", "u14", "u15", "u16", "u17", "u18"]):
        return "field_standards"
    
    return "generic"


@dataclass
class NLUResult:
    intent: str
    confidence: float
    slots: Dict[str, Any]
    template_hint: Optional[str]


def classify_intent_and_slots(
    text: str, image_uri: Optional[str] = None
) -> NLUResult:
    q = text.strip()
    q_emb = _ENCODER.encode([q], normalize_embeddings=True)
    sims = util.cos_sim(q_emb, _PROT_EMB).cpu().tolist()[0]

    # TOP-1 prototype
    best_i = max(range(len(sims)), key=lambda i: sims[i])
    best_label = _PROT_LABELS[best_i]
    best_score = float(sims[best_i])

    # CRITICAL: Only use CV if image is actually uploaded
    print(f"[NLU-DEBUG] Initial intent from similarity: {best_label}")
    print(f"[NLU-DEBUG] Image URI provided: {image_uri}")
    
    if image_uri:
        print(f"[NLU-DEBUG] Image detected, adding CV to intent")
        if "RAG" in best_label or "SQL" in best_label:
            best_label = "RAG+CV_tool"
        else:
            best_label = "CV_tool"
    else:
        if "CV" in best_label:
            print(f"[NLU-DEBUG] No image but CV intent detected, forcing to RAG")
            best_label = "RAG"
    
    print(f"[NLU-DEBUG] Final intent after image check: {best_label}")

    # Extract entities
    domain = _detect_domain(q)
    month, year = _parse_month_year(q)
    s_m, e_m, r_y = _parse_month_range(q)
    park = _parse_park(q)

    slots: Dict[str, Any] = {
        "domain": domain,
        "month": month,
        "year": year,
        "start_month": s_m,
        "end_month": e_m,
        "range_year": r_y,
        "park_name": park,
        "image_uri": image_uri,
    }

    # -------- Template routing --------
    template_hint = None
    lowq = _norm(q)
    
    if domain == "mowing":
        # Priority order: most specific patterns first
        if any(k in lowq for k in ["highest", "top", "max", "most expensive"]) and "cost" in lowq:
            template_hint = "mowing.labor_cost_month_top1"
        elif any(k in lowq for k in ["last", "recent", "latest", "when was"]) and any(k in lowq for k in ["mow", "mowing"]):
            template_hint = "mowing.last_mowing_date"
        elif "trend" in lowq and "cost" in lowq:
            template_hint = "mowing.cost_trend"
        elif re.search(r'\bfrom\s+\w+\s+to\s+\w+', lowq) and "cost" in lowq:
            template_hint = "mowing.cost_trend"
        elif any(k in lowq for k in ["compare", "across", "all parks"]) and "cost" in lowq:
            template_hint = "mowing.cost_by_park_month"
        elif any(k in lowq for k in ["breakdown", "detail", "break down"]):
            template_hint = "mowing.cost_breakdown"
        elif "by park" in lowq or "each park" in lowq:
            template_hint = "mowing.cost_by_park_month"

    # RAG-only triggers - force RAG for informational queries
    if any(k in lowq for k in ["steps", "procedure", "safety", "manual", "how to", "sop",
                                "dimensions", "requirements", "standards", "what are", "show me", "tell me"]):
        if "SQL" not in best_label and not image_uri:
            print(f"[NLU-DEBUG] RAG keywords detected, forcing to RAG")
            best_label = "RAG"

    print(f"[NLU] Query: '{q}'")
    print(f"[NLU] Domain: {domain}")
    print(f"[NLU] Intent: {best_label} (confidence: {best_score:.3f})")
    print(f"[NLU] Slots: {slots}")
    print(f"[NLU] Template hint: {template_hint}")
    print(f"[NLU] Image uploaded: {'Yes' if image_uri else 'No'}")

    return NLUResult(
        intent=best_label,
        confidence=round(best_score, 3),
        slots=slots,
        template_hint=template_hint,
    )


def build_route_plan(nlu_result: NLUResult, original_query: str = "") -> List[Dict[str, Any]]:
    """Build tool execution plan based on NLU result"""
    plan: List[Dict[str, Any]] = []
    intent = nlu_result.intent
    slots = nlu_result.slots
    template_hint = nlu_result.template_hint
    
    # CRITICAL FIX: Force remove CV if no image
    if "CV" in intent and not slots.get("image_uri"):
        print(f"[NLU] WARNING: CV intent detected but no image provided, forcing to RAG")
        if intent == "RAG+CV_tool":
            intent = "RAG"
        elif intent == "CV_tool":
            intent = "RAG"

    if intent == "RAG":
        # Detect query type for better keyword selection
        q_lower = _norm(original_query or "")
        
        # Field dimensions query
        if any(k in q_lower for k in ["dimension", "size", "requirement", "standard", "soccer", "baseball", "softball", "cricket", "football", "rugby", "field", "u10", "u11", "u12", "u13", "u14", "u15", "u16", "u17", "u18", "pitching", "distance"]):
            query_keywords = "field dimensions standards age group requirements length width pitching distance soccer baseball softball"
            print(f"[NLU] Detected FIELD DIMENSIONS query")
        else:
            # Mowing procedures query
            query_keywords = "mowing standard safety equipment frequency lane kilometer pricing"
            print(f"[NLU] Detected MOWING PROCEDURES query")
        
        plan.append({
            "tool": "kb_retrieve",
            "args": {
                "query": query_keywords,
                "top_k": 5
            }
        })
        plan.append({
            "tool": "sop_extract",
            "args": {
                "schema": ["steps", "materials", "tools", "safety"]
            }
        })
        print(f"[NLU] Plan: RAG workflow (keywords='{query_keywords}')")

    elif intent == "SQL_tool":
        template = template_hint or "mowing.labor_cost_month_top1"
        
        params = {
            "month": slots.get("month"),
            "year": slots.get("year"),
            "park_name": slots.get("park_name"),
        }
        
        if template == "mowing.cost_trend":
            params["year"] = slots.get("range_year") or slots.get("year")
            params["start_month"] = slots.get("start_month") or slots.get("month") or 1
            params["end_month"] = slots.get("end_month") or slots.get("month") or 12
            params.pop("month", None)
        
        plan.append({
            "tool": "sql_query_rag",
            "args": {
                "template": template,
                "params": params
            }
        })
        print(f"[NLU] Plan: SQL workflow (template={template}, params={params})")

    elif intent == "RAG+SQL_tool":
        plan.append({
            "tool": "kb_retrieve",
            "args": {
                "query": "mowing cost labor standard pricing rate",
                "top_k": 3
            }
        })
        
        template = template_hint or "mowing.labor_cost_month_top1"
        params = {
            "month": slots.get("month"),
            "year": slots.get("year"),
            "park_name": slots.get("park_name"),
        }
        
        plan.append({
            "tool": "sql_query_rag",
            "args": {
                "template": template,
                "params": params
            }
        })
        print(f"[NLU] Plan: RAG+SQL workflow (kb_retrieve + template={template})")

    elif intent == "CV_tool":
        plan.append({
            "tool": "cv_assess_rag",
            "args": {
                "image_uri": slots.get("image_uri"),
                "topic_hint": "turf wear disease inspection guidelines"
            }
        })
        print(f"[NLU] Plan: CV workflow (cv_assess_rag)")

    elif intent == "RAG+CV_tool":
        plan.append({
            "tool": "kb_retrieve",
            "args": {
                "query": "turf inspection maintenance repair standards",
                "top_k": 3
            }
        })
        plan.append({
            "tool": "cv_assess_rag",
            "args": {
                "image_uri": slots.get("image_uri"),
                "topic_hint": "turf wear disease inspection guidelines"
            }
        })
        print(f"[NLU] Plan: RAG+CV workflow (kb_retrieve + cv_assess_rag)")

    return plan


def nlu_parse(text: str, image_uri: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry: parse user input, return intent, slots, and execution plan
    
    Returns:
        {
            "intent": str,
            "confidence": float,
            "slots": dict,
            "route_plan": list,
            "clarifications": list
        }
    """
    nlu_result = classify_intent_and_slots(text, image_uri)
    plan = build_route_plan(nlu_result, original_query=text)  # ✅ Pass original query
    
    # CRITICAL FIX: Final check for CV without image
    final_intent = nlu_result.intent
    if "CV" in final_intent and not image_uri:
        print(f"[NLU] FINAL CHECK: Removing CV from intent (no image)")
        if final_intent == "RAG+CV_tool":
            final_intent = "RAG"
        elif final_intent == "CV_tool":
            final_intent = "RAG"
    
    # Generate clarifications
    clarifications = []
    if final_intent in ["SQL_tool", "RAG+SQL_tool"]:
        template = nlu_result.template_hint
        
        if template == "mowing.cost_trend":
            if not nlu_result.slots.get("start_month") or not nlu_result.slots.get("end_month"):
                clarifications.append("Which time period would you like to see? (e.g., from January to June)")
        elif template in ["mowing.cost_by_park_month", "mowing.cost_breakdown", "mowing.labor_cost_month_top1"]:
            if not nlu_result.slots.get("month") or not nlu_result.slots.get("year"):
                clarifications.append("Which month and year would you like to query?")
        elif template == "mowing.last_mowing_date":
            if not nlu_result.slots.get("park_name"):
                clarifications.append("Which park would you like to check? (or say 'all parks')")
    
    return {
        "intent": final_intent,  # ✅ Use corrected intent
        "confidence": nlu_result.confidence,
        "slots": nlu_result.slots,
        "route_plan": plan,
        "clarifications": clarifications
    }