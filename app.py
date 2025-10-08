from __future__ import annotations
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

# =========================
# 0) Domain dictionaries
# =========================
ASSET_TYPE_ALIASES = {
    "sports_field": ["sports field", "field", "pitch", "soccer field", "ball field"],
    "turf": ["turf", "grass", "lawn"],
    "horticulture": ["horticulture", "bed", "garden"],
}

SPORT_ALIASES = {
    "soccer": ["soccer", "football"],
    "softball": ["softball"],
    "baseball": ["baseball"],
}

AGE_ALIASES = {
    "U13": ["u13", "under 13"],
    "U11": ["u11", "under 11"],
    "Adult": ["adult", "senior"],
}

PARK_ALIASES = {
    "Queen Elizabeth Park": ["queen elizabeth park", "qe park"],
    "Stanley Park": ["stanley park", "stanley"],
}

DISTRICT_ALIASES = {
    "West": ["west district", "west"],
    "East": ["east district", "east"],
    "South": ["south district", "south"],
    "North": ["north district", "north"],
}

# 简单的“默认阈值/参数”，真实项目里可来自 KB 或配置表
DEFAULTS = {
    "mowing_overdue_days": 7,
    "permit_lookback_years": 2,
}

# =========================
# 1) Small helpers
# =========================
def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _contains_any(text: str, words: List[str]) -> bool:
    t = _norm(text)
    return any(w in t for w in words)

def _map_alias(text: str, alias_map: Dict[str, List[str]]) -> Optional[str]:
    t = _norm(text)
    for k, vs in alias_map.items():
        if _norm(k) in t:
            return k
        for v in vs:
            if _norm(v) in t:
                return k
    return None

def _parse_int(text: str, pattern: str) -> Optional[int]:
    m = re.search(pattern, _norm(text))
    return int(m.group(1)) if m else None

def _parse_month(text: str) -> Optional[str]:
    # naive: pick 3-letter month tokens (sep, september)
    t = _norm(text)
    months = {
        "jan": "01", "january": "01",
        "feb": "02", "february": "02",
        "mar": "03", "march": "03",
        "apr": "04", "april": "04",
        "may": "05",
        "jun": "06", "june": "06",
        "jul": "07", "july": "07",
        "aug": "08", "august": "08",
        "sep": "09", "sept": "09", "september": "09",
        "oct": "10", "october": "10",
        "nov": "11", "november": "11",
        "dec": "12", "december": "12",
    }
    for k, v in months.items():
        if k in t:
            year = _parse_int(t, r"\b(20\d{2})\b") or datetime.utcnow().year
            return f"{year}-{v}"
    return None

# =========================
# 2) Intent classification
# (updated to new 4+1 intents)
# =========================
INTENTS = [
    "FIELD_MOD_FEASIBILITY",   # 场地改造/重分类可行性（基于标准）
    "MAINTENANCE_SLA",         # 维护合规（turf/hort）
    "PERMIT_IMPACT",           # 许可影响分析
    "LABOR_DASHBOARD",         # 劳务编码质量/成本视图
    "IMAGE_ASSESS",            # （可选）图像评估
    "OTHER",
]

def classify_intent(text: str, image_uri: Optional[str]) -> (str, float):
    t = _norm(text)

    # 图片驱动
    if image_uri or _contains_any(t, ["photo", "image", "picture", "upload"]):
        if _contains_any(t, ["disease", "wear", "bare", "weed", "rust", "crack", "check this"]):
            return "IMAGE_ASSESS", 0.85
        return "IMAGE_ASSESS", 0.70

    # 场地改造/可行性：soccer/softball/baseball + “fit/adjust/meet standard/diamond/resize”
    if (_map_alias(t, SPORT_ALIASES) and
        _contains_any(t, ["fit", "adjust", "resize", "meet size standard", "meet standard", "diamond"])):
        return "FIELD_MOD_FEASIBILITY", 0.85

    # 维护合规：turf/horticulture + overdue/frequency/mowing/pruning + group by
    if (_contains_any(t, ["turf", "horticulture", "mowing", "pruning", "overdue", "frequency"]) or
        _map_alias(t, DISTRICT_ALIASES)):
        return "MAINTENANCE_SLA", 0.80

    # 许可影响：permit hours / affected / upgrade/close
    if _contains_any(t, ["permit", "affected", "upgrade", "close", "closure", "two years"]):
        return "PERMIT_IMPACT", 0.80

    # 劳务视图：mowing labor code / mismatched / crews / cost per hectare
    if _contains_any(t, ["labor code", "mismatched", "miscoding", "crews", "cost per hectare", "sap"]):
        return "LABOR_DASHBOARD", 0.85

    return "OTHER", 0.50

# =========================
# 3) Slot extraction
# =========================
def extract_slots(text: str, image_uri: Optional[str]) -> Dict[str, Any]:
    t = _norm(text)
    slots: Dict[str, Any] = {
        "asset_type": None,
        "sport": None,
        "age_group": None,
        "park_name": None,
        "district": None,
        "overdue_days": None,
        "month": None,
        "years_lookback": None,
        "field_id": None,
        "image_uri": image_uri,
        "limit": _parse_int(t, r"\btop\s+(\d{1,3})\b") or 100,
    }

    # asset scope
    slots["asset_type"] = _map_alias(t, ASSET_TYPE_ALIASES)

    # sport + age
    slots["sport"] = _map_alias(t, SPORT_ALIASES)
    slots["age_group"] = _map_alias(t, AGE_ALIASES)

    # park & district
    slots["park_name"] = _map_alias(t, PARK_ALIASES)
    slots["district"] = _map_alias(t, DISTRICT_ALIASES)

    # overdue days
    days = _parse_int(t, r"\boverdue\s+by\s+(\d{1,3})\s+days\b")
    if days is None:
        days = _parse_int(t, r"\bmore than\s+(\d{1,3})\s+days\b")
    slots["overdue_days"] = days or DEFAULTS["mowing_overdue_days"]

    # month (for labor dashboard filter)
    slots["month"] = _parse_month(t)

    # years lookback (for permit impact)
    yl = _parse_int(t, r"\blast\s+(\d)\s+years\b") or _parse_int(t, r"\bpast\s+(\d)\s+years\b")
    slots["years_lookback"] = yl or DEFAULTS["permit_lookback_years"]

    # field id (if user mentions a specific one)
    m = re.search(r"\bfield\s*([A-Za-z0-9\-]+)\b", t)
    if m: slots["field_id"] = m.group(1)

    return slots

# =========================
# 4) Plan builder (tool routing)
# =========================
def build_route_plan(intent: str, slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    if intent == "FIELD_MOD_FEASIBILITY":
        # 先拉出相关标准（运动/年龄段），再进行空间/尺寸校验
        std_query = f"{slots.get('sport') or 'sport'} {slots.get('age_group') or ''} field size standard".strip()
        plan.append({"tool": "kb_retrieve", "args": {"query": std_query, "top_k": 3}})
        plan.append({"tool": "sql_query", "args": {
            "template": "field_mod_feasibility",
            "params": {
                "sport": slots.get("sport"),
                "age_group": slots.get("age_group"),
                "park_name": slots.get("park_name"),
                "limit": slots.get("limit"),
            }
        }})
    elif intent == "MAINTENANCE_SLA":
        # 找到频次/阈值，再做合规性对比
        plan.append({"tool": "kb_retrieve", "args": {"query": "turf horticulture maintenance frequency standard", "top_k": 3}})
        plan.append({"tool": "sop_extract", "args": {"schema": ["frequency", "season", "threshold_days"]}})
        plan.append({"tool": "sql_query", "args": {
            "template": "turf_hort_overdue",
            "params": {
                "district": slots.get("district"),
                "overdue_days": slots.get("overdue_days"),
                "limit": slots.get("limit"),
            }
        }})
    elif intent == "PERMIT_IMPACT":
        plan.append({"tool": "sql_query", "args": {
            "template": "permit_impact",
            "params": {
                "field_id": slots.get("field_id"),
                "years_lookback": slots.get("years_lookback"),
                "park_name": slots.get("park_name"),
            }
        }})
        # 可选：检索规则说明（作为引用）
        plan.append({"tool": "kb_retrieve", "args": {"query": "permitting policy and reallocation rules", "top_k": 2}})
    elif intent == "LABOR_DASHBOARD":
        plan.append({"tool": "kb_retrieve", "args": {"query": "mowing labor coding rules", "top_k": 2}})
        plan.append({"tool": "sql_query", "args": {
            "template": "labor_miscoding",
            "params": {
                "month": slots.get("month"),
                "district": slots.get("district"),
            }
        }})
    elif intent == "IMAGE_ASSESS":
        plan.append({"tool": "cv_assess", "args": {"image_uri": slots.get("image_uri"), "asset_type": slots.get("asset_type")}})
    else:
        plan.append({"tool": "kb_retrieve", "args": {"query": "project scope faq", "top_k": 2}})
    return plan

# =========================
# 5) NLU public
# =========================
def nlu_parse(text: str, image_uri: Optional[str] = None) -> Dict[str, Any]:
    intent, conf = classify_intent(text, image_uri)
    slots = extract_slots(text, image_uri)
    plan = build_route_plan(intent, slots)
    clar = []
    if conf < 0.65:
        clar.append("I'm not fully sure which analysis you want: field feasibility, maintenance SLA, permit impact, labor dashboard, or image assessment?")
    if intent in ("FIELD_MOD_FEASIBILITY", "PERMIT_IMPACT") and not slots.get("sport"):
        clar.append("Which sport is this about (soccer, softball, baseball)?")
    return {"intent": intent, "confidence": round(conf, 2), "slots": slots, "route_plan": plan, "clarifications": clar}

# =========================
# 6) Mock tools (replace later)
# =========================
def kb_retrieve(query: str, top_k: int = 3, filters: Optional[dict] = None):
    # 简单样例，真实项目请接向量检索/关键字检索
    if "size standard" in query:
        hits = [
            {"doc_id":"std001","chunk_id":"c1","text":"U13 soccer field: 90-100m x 45-64m; runoff ≥ 1.5m.","page":2,"image_ref":None,"score":0.92,"source":"consultant/standards_soccer.xlsx#U13"},
        ]
    elif "maintenance frequency" in query:
        hits = [
            {"doc_id":"std010","chunk_id":"c2","text":"Turf mowing frequency: every 7–10 days in growing season.","page":1,"image_ref":None,"score":0.90,"source":"policy/turf_standards.pdf#p1"},
        ]
    elif "mowing labor coding rules" in query:
        hits = [
            {"doc_id":"kb020","chunk_id":"c3","text":"Mowing codes must match park asset types. Non-park or other activities should not be used for turf mowing.","page":3,"image_ref":None,"score":0.88,"source":"kb/labor_coding.md#rules"},
        ]
    else:
        hits = [
            {"doc_id":"kb000","chunk_id":"c0","text":"Project scope and FAQ placeholder.","page":1,"image_ref":None,"score":0.50,"source":"kb/faq.md"},
        ]
    return {"hits": hits[:top_k]}

def sop_extract(snippets: List[str], schema: List[str]):
    # 从 snippets 中抽“频次/阈值”等：这里直接 mock
    return {
        "frequency": "7-10 days (growing season)",
        "season": "Apr–Oct",
        "threshold_days": 7
    }

def sql_query(template: str, params: Dict[str, Any]):
    t0 = time.time()
    if template == "field_mod_feasibility":
        rows = [
            {"field_id":"SF-101","park":"Stanley Park","sport":"soccer","age_group": params.get("age_group") or "U13",
             "meets_now": False, "min_change_needed":"widen by 2m; add runoff 1m", "feasibility_score": 0.78},
            {"field_id":"SF-115","park":"Queen Elizabeth Park","sport":"soccer","age_group": params.get("age_group") or "U13",
             "meets_now": True, "min_change_needed":"none", "feasibility_score": 0.92},
        ]
    elif template == "turf_hort_overdue":
        rows = [
            {"polygon_id":"T-9001","district": params.get("district") or "West","days_since_mow": 11,"status":"overdue"},
            {"polygon_id":"T-9012","district": params.get("district") or "West","days_since_mow": 3,"status":"ok"},
        ]
    elif template == "permit_impact":
        rows = [
            {"field_id": params.get("field_id") or "SF-101","years_lookback": params.get("years_lookback") or 2,
             "affected_hours": 186, "peak_month":"June","note":"Consider relocation to SF-115"},
        ]
    elif template == "labor_miscoding":
        rows = [
            {"park":"Stanley Park","month": params.get("month") or "2025-09","code":"MOW-OTHER","hours": 42,"mismatch": True},
            {"park":"QE Park","month": params.get("month") or "2025-09","code":"MOW-TURF","hours": 210,"mismatch": False},
        ]
    else:
        rows = []
    time.sleep(0.02)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": int((time.time()-t0)*1000)}

def cv_assess(image_uri: str, asset_type: Optional[str]):
    # 视觉评估：先返回占位
    return {
        "condition": "wear_signs",
        "score": 0.64,
        "labels": ["bare_patch", "weed_presence"],
        "explanations": ["Low coverage in center", "Texture anomaly on left"],
        "low_confidence": False
    }

TOOL_REGISTRY = {
    "kb_retrieve": kb_retrieve,
    "sop_extract": sop_extract,
    "sql_query": sql_query,
    "cv_assess": cv_assess,
}

# =========================
# 7) Agent executor & composer
# =========================
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

def compose_answer(nlu: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    intent = nlu.get("intent")
    slots = nlu.get("slots", {})
    ev = state["evidence"]
    logs = state["logs"]

    answer_md = ""
    tables: List[Dict[str, Any]] = []
    map_layer = None
    citations: List[Dict[str, Any]] = []

    if intent == "FIELD_MOD_FEASIBILITY":
        rows = ev["sql"].get("rows", [])
        tables.append({"name": "feasibility", "columns": list(rows[0].keys()) if rows else [], "rows": rows})
        answer_md = (
            f"**Field Modification Feasibility** — sport={slots.get('sport') or 'n/a'}, "
            f"age_group={slots.get('age_group') or 'n/a'}\n\n"
            f"Returned **{ev['sql'].get('rowcount',0)}** candidates in **{ev['sql'].get('elapsed_ms',0)}ms**."
        )
        for h in ev["kb_hits"]:
            citations.append({"title": "Standard", "source": h["source"]})

    elif intent == "MAINTENANCE_SLA":
        rows = ev["sql"].get("rows", [])
        tables.append({"name": "turf_hort_sla", "columns": list(rows[0].keys()) if rows else [], "rows": rows})
        th = ev["sop"].get("threshold_days") or slots.get("overdue_days")
        answer_md = (
            f"**Maintenance SLA Check** — district={slots.get('district') or 'all'}, "
            f"threshold={th} days\n\n"
            f"Returned **{ev['sql'].get('rowcount',0)}** rows in **{ev['sql'].get('elapsed_ms',0)}ms**."
        )
        for h in ev["kb_hits"]:
            citations.append({"title": "Maintenance standard", "source": h["source"]})

    elif intent == "PERMIT_IMPACT":
        rows = ev["sql"].get("rows", [])
        tables.append({"name": "permit_impact", "columns": list(rows[0].keys()) if rows else [], "rows": rows})
        answer_md = (
            f"**Permit Impact** — field={slots.get('field_id') or 'n/a'}, "
            f"lookback={slots.get('years_lookback')} years\n\n"
            f"Returned **{ev['sql'].get('rowcount',0)}** scenario(s)."
        )
        for h in ev["kb_hits"]:
            citations.append({"title": "Permitting policy", "source": h["source"]})

    elif intent == "LABOR_DASHBOARD":
        rows = ev["sql"].get("rows", [])
        tables.append({"name": "labor_miscoding", "columns": list(rows[0].keys()) if rows else [], "rows": rows})
        answer_md = (
            f"**Labor Coding Dashboard** — month={slots.get('month') or 'current'}, "
            f"district={slots.get('district') or 'all'}\n\n"
            f"Returned **{ev['sql'].get('rowcount',0)}** records."
        )
        for h in ev["kb_hits"]:
            citations.append({"title": "Coding rules", "source": h["source"]})

    elif intent == "IMAGE_ASSESS":
        cv = ev["cv"]
        answer_md = (
            f"**Image Assessment**\n\n"
            f"Condition label: **{cv.get('condition','unknown')}** "
            f"(score {cv.get('score',0):.2f})\n\n"
            f"Labels: {', '.join(cv.get('labels', []))}\n\n"
            f"Notes: {'; '.join(cv.get('explanations', []))}"
        )
        if cv.get("low_confidence"):
            answer_md = "> ⚠ Low confidence — consider another angle.\n\n" + answer_md

    else:
        answer_md = "I couldn't map this to a known workflow. Try field feasibility, maintenance SLA, permit impact, labor dashboard, or attach a photo."

    return {
        "answer_md": answer_md,
        "tables": tables,
        "map_layer": map_layer,
        "citations": citations,
        "logs": logs
    }

# =========================
# 8) HTTP layer
# =========================
class NLUReq(BaseModel):
    text: str
    image_uri: Optional[str] = None

class AgentReq(BaseModel):
    text: str
    image_uri: Optional[str] = None
    nlu: Optional[Dict[str, Any]] = None

app = FastAPI(title="Parks Prototype API", version="0.2.0")

# CORS
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