
from __future__ import annotations
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

# -----------------------------
# NLU (rule-based v0, English only)
# 可以用更复杂的模型替换
# -----------------------------
ASSET_TYPE_ALIASES = {
    "bench": ["bench", "benches"],
    "playground": ["playground", "playgrounds"],
    "trail": ["trail", "trails", "path", "paths", "walkway", "walkways"],
    "parking_lot": ["parking lot", "parking", "car park"],
}
PARK_ALIASES = {
    "Queen Elizabeth Park": ["queen elizabeth park", "qe park"],
    "Stanley Park": ["stanley park", "stanley"],
}
DEFAULT_INSPECTION_THRESHOLD = {
    "playground": 180,
    "bench": 270,
    "trail": 365,
    "parking_lot": 365,
    "_default": 300,
}

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _guess_type(t: str) -> Optional[str]:
    if "bench" in t: return "bench"
    if "playground" in t or "slide" in t or "swing" in t: return "playground"
    if "trail" in t or "path" in t or "walkway" in t: return "trail"
    if "parking" in t: return "parking_lot"
    return None

def _find_park_name(text: str) -> Optional[str]:
    t = _norm(text)
    for canonical, aliases in PARK_ALIASES.items():
        cand = [canonical] + aliases
        for c in cand:
            if _norm(c) in t:
                return canonical
    return None

def _parse_limit(text: str) -> Optional[int]:
    m = re.search(r"\btop\s+(\d{1,3})\b", _norm(text))
    return int(m.group(1)) if m else None

def classify_intent(text: str, image_uri: Optional[str]) -> (str, float):
    t = _norm(text)
    if image_uri:
        if re.search(r"(need repair|does this|check this|is this broken|does it need maintenance)", t):
            return "IMAGE_ASSESS", 0.85
        return "IMAGE_ASSESS", 0.70
    if re.search(r"(how to|what steps|procedure).*(service|repair|maintain|maintenance)", t):
        return "SOP_QUERY", 0.85
    if re.search(r"(overdue|need.*inspection|due for inspection|past due)", t):
        return "DATA_QUERY", 0.80
    return "DATA_QUERY", 0.60

def extract_slots(text: str, image_uri: Optional[str]) -> Dict[str, Any]:
    t = _norm(text)
    asset_type = _guess_type(t)
    park = _find_park_name(t)
    limit = _parse_limit(t) or 100
    threshold = DEFAULT_INSPECTION_THRESHOLD.get(asset_type or "", DEFAULT_INSPECTION_THRESHOLD["_default"])
    return {
        "asset_type": asset_type,
        "location": {"park_name": park} if park else None,
        "inspection_threshold_days": threshold,
        "limit": limit,
        "image_uri": image_uri,
        "analysis_type": "overdue"
    }

def build_route_plan(intent: str, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    if intent == "SOP_QUERY":
        plan.append({"tool": "kb_retrieve", "args": {"query": f"maintenance steps {slots.get('asset_type') or 'asset'}", "top_k": 3}})
        plan.append({"tool": "sop_extract", "args": {"schema": ["steps", "materials", "tools", "safety"]}})
    elif intent == "IMAGE_ASSESS":
        plan.append({"tool": "cv_assess", "args": {"image_uri": slots.get("image_uri"), "asset_type": slots.get("asset_type")}})
    else:  # DATA_QUERY default
        plan.append({"tool": "sql_query", "args": {
            "template": "assets_overdue_by_type_and_park",
            "params": {
                "type": slots.get("asset_type"),
                "park_name": (slots.get("location") or {}).get("park_name") or "Stanley Park",
                "threshold_days": slots.get("inspection_threshold_days"),
                "limit": slots.get("limit"),
            }
        }})
    return plan

def nlu_parse(text: str, image_uri: Optional[str] = None) -> Dict[str, Any]:
    intent, conf = classify_intent(text, image_uri)
    slots = extract_slots(text, image_uri)
    plan = build_route_plan(intent, slots)
    clar = []
    if conf < 0.65:
        clar.append("I'm not fully sure about the intent. Do you want inspection data, maintenance steps, or an image assessment?")
    if not slots.get("asset_type") and intent != "IMAGE_ASSESS":
        clar.append("Which asset type do you mean (playground, bench, trail, parking lot)?")
    return {"intent": intent, "confidence": round(conf, 2), "slots": slots, "route_plan": plan, "clarifications": clar}

# -----------------------------
# Mock tools (replace later)
# -----------------------------
def kb_retrieve(query: str, top_k: int = 3, filters: Optional[dict] = None):
    hits = [
        {"doc_id":"kb001","chunk_id":"c1","text":"Playground inspection must occur every 180 days.",
         "page":4,"image_ref":None,"score":0.92,"source":"kb_manuals/playground_sop.pdf#p4"},
        {"doc_id":"kb001","chunk_id":"c2","text":"Always lock out moving parts before servicing a slide.",
         "page":5,"image_ref":None,"score":0.88,"source":"kb_manuals/playground_sop.pdf#p5"},
    ][:top_k]
    return {"hits": hits}

def sop_extract(snippets: List[str], schema: List[str]):
    steps = [
        "Inspect slide surface for cracks and sharp edges.",
        "Clean debris; tighten loose bolts.",
        "Lubricate moving joints; replace damaged parts.",
    ]
    return {
        "steps": steps,
        "materials": ["lubricant", "replacement bolts", "cleaning kit"],
        "tools": ["socket wrench", "torque wrench"],
        "safety": ["Lockout moving parts; wear gloves and eye protection."]
    }

def sql_query(template: str, params: Dict[str, Any]):
    rows = [
        {"asset_id":"pg-001","name":"Playground A","park": params.get("park_name","Stanley Park"),
         "last_inspected_at":"2024-12-15","days_overdue": 95, "replacement_cost": 12000},
        {"asset_id":"pg-007","name":"Playground B","park": params.get("park_name","Stanley Park"),
         "last_inspected_at":"2024-10-01","days_overdue": 170, "replacement_cost": 18000},
    ]
    t0 = time.time()
    time.sleep(0.02)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": int((time.time()-t0)*1000)}

def cv_assess(image_uri: str, asset_type: Optional[str]):
    return {
        "condition": "fair",
        "score": 0.62,
        "labels": ["paint_peel", "surface_wear"],
        "explanations": ["Edge wear detected", "Color fading"],
        "low_confidence": False
    }

TOOL_REGISTRY = {
    "kb_retrieve": kb_retrieve,
    "sop_extract": sop_extract,
    "sql_query": sql_query,
    "cv_assess": cv_assess,
}

# -----------------------------
# Agent executor
# -----------------------------
def execute_plan(plan: List[Dict[str, Any]], slots: Dict[str, Any]) -> Dict[str, Any]:
    state = {
        "slots": slots,
        "plan": plan,
        "evidence": {"kb_hits": [], "sop": {}, "sql": {}, "cv": {}},
        "logs": []
    }
    for step in plan:
        tool = step["tool"]
        args = step.get("args", {}) or {}
        t0 = time.time()
        try:
            if tool == "kb_retrieve":
                out = TOOL_REGISTRY[tool](**args)
                state["evidence"]["kb_hits"] = out["hits"]
            elif tool == "sop_extract":
                snippets = [h["text"] for h in state["evidence"]["kb_hits"]]
                out = TOOL_REGISTRY[tool](snippets=snippets, **args)
                state["evidence"]["sop"] = out
            elif tool == "sql_query":
                out = TOOL_REGISTRY[tool](**args)
                state["evidence"]["sql"] = out
            elif tool == "cv_assess":
                out = TOOL_REGISTRY[tool](**args)
                state["evidence"]["cv"] = out
            else:
                out = {"_warn": f"Unknown tool {tool}"}
            ok, err = True, None
        except Exception as e:
            ok, err = False, str(e)
            out = {"error": err}
        state["logs"].append({
            "tool": tool,
            "args_redacted": list(args.keys()),
            "elapsed_ms": int((time.time()-t0)*1000),
            "ok": ok, "err": err
        })
    return state

# -----------------------------
# Answer composer
# -----------------------------
def compose_answer(nlu: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    intent = nlu.get("intent")
    slots = nlu.get("slots", {})
    ev = state["evidence"]
    logs = state["logs"]

    answer_md = ""
    tables: List[Dict[str, Any]] = []
    map_layer = None
    citations: List[Dict[str, Any]] = []

    if intent == "SOP_QUERY":
        sop = ev["sop"]
        answer_md = (
            f"**Maintenance SOP for {slots.get('asset_type') or 'asset'}**\n\n"
            "### Steps\n" + "\n".join([f"{i+1}. {s}" for i, s in enumerate(sop.get('steps', []))]) +
            "\n\n### Materials\n- " + "\n- ".join(sop.get("materials", [])) +
            "\n\n### Tools\n- " + "\n- ".join(sop.get("tools", [])) +
            "\n\n### Safety\n- " + "\n- ".join(sop.get("safety", []))
        )
        for h in ev["kb_hits"]:
            citations.append({"title": "Manual snippet", "source": h["source"]})

    elif intent == "DATA_QUERY":
        sql = ev["sql"]
        rows = sql.get("rows", [])
        tables.append({
            "name": "results",
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows
        })
        analysis = slots.get("analysis_type", "overdue")
        answer_md = (
            f"**Data query: {analysis}**\n\n"
            f"Returned **{sql.get('rowcount',0)}** rows in **{sql.get('elapsed_ms',0)}ms**."
        )

    elif intent == "IMAGE_ASSESS":
        cv = ev["cv"]
        answer_md = (
            f"**Image Assessment**\n\n"
            f"Condition: **{cv.get('condition','unknown')}** (score {cv.get('score',0):.2f})\n\n"
            f"Labels: {', '.join(cv.get('labels', []))}\n\n"
            f"Notes: {'; '.join(cv.get('explanations', []))}"
        )
        if cv.get("low_confidence"):
            answer_md = "> ⚠ Low confidence — consider uploading another angle.\n\n" + answer_md

    else:
        answer_md = "I couldn't map this to a known workflow. Try asking for inspection, SOP, or attach a photo."

    return {
        "answer_md": answer_md,
        "tables": tables,
        "map_layer": map_layer,
        "citations": citations,
        "logs": logs
    }

# -----------------------------
# FastAPI HTTP layer
# -----------------------------
class NLUReq(BaseModel):
    text: str
    image_uri: Optional[str] = None

class AgentReq(BaseModel):
    text: str
    image_uri: Optional[str] = None
    nlu: Optional[Dict[str, Any]] = None

app = FastAPI(title="Parks Prototype API", version="0.1.0")
# 加 CORS 中间件
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@app.post("/nlu/parse")
def nlu_endpoint(req: NLUReq):
    return nlu_parse(req.text, req.image_uri)

@app.post("/agent/answer")
def agent_answer(req: AgentReq):
    nlu = req.nlu or nlu_parse(req.text, req.image_uri)
    state = execute_plan(nlu["route_plan"], nlu["slots"])
    return compose_answer(nlu, state)
