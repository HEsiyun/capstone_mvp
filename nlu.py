# nlu.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

from sentence_transformers import SentenceTransformer, util

# ---------- MiniLM encoder ----------
_ENCODER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ---------- Few-shot prototypes ----------
# 每个意图给若干原型句，使用语义相似度（cosine）投票
INTENT_PROTOTYPES = {
    "RAG+SQL_tool": [
        "Which park had the highest total mowing labor cost in March 2025?",
        "Show me the most expensive park for mowing in April",
        "What was the top mowing cost by location last month?",
    ],
    "RAG": [
        "What are the mowing steps and safety requirements?",
        "How do I maintain the turf properly?",
        "What equipment do I need for mowing?",
        "Tell me the standard operating procedures for mowing",
    ],
    "SQL_tool": [
        # 趋势分析
        "How did total mowing costs trend from April to June 2025?",
        "Show mowing cost trend from January to March",
        "What's the cost trend for Cambridge Park over time?",
        
        # 对比分析
        "Compare mowing costs across all parks in March 2025",
        "Show me all parks ranked by mowing cost",
        "What's the cost breakdown by park?",
        
        # 最近活动
        "When was the last mowing at Cambridge Park?",
        "Show me the most recent mowing date for each park",
        "Which parks haven't been mowed recently?",
        
        # 详细分解
        "Show total mowing costs breakdown by park in March 2025",
        "What's the cost breakdown for Garden Park?",
    ],
    "RAG+CV_tool": [
        "Here is a picture. What's the estimated labour cost to repair the turf?",
        "Here is a picture. Help me plan the layout of this sports field effectively.",
        "Check this image and tell me if the grass needs mowing",
    ],
    "CV_tool": [
        "Check this image and assess turf condition.",
        "Analyze this photo of the field",
    ],
}

# 预编码
_PROT_TEXTS: List[str] = []
_PROT_LABELS: List[str] = []
for label, samples in INTENT_PROTOTYPES.items():
    for s in samples:
        _PROT_TEXTS.append(s)
        _PROT_LABELS.append(label)
_PROT_EMB = _ENCODER.encode(_PROT_TEXTS, normalize_embeddings=True)

# ---------- month/year & park 解析 ----------
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

    # abbr month (Apr, Jun…)
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
    解析月份范围或单个月份
    返回: (start_month, end_month, year)
    
    支持模式:
    - "from April to June 2025" -> (4, 6, 2025)
    - "in June 2025" -> (6, 6, 2025)  # 单月
    - "trend in March" -> (3, 3, None)
    """
    t = _norm(text)
    
    # 模式1: 明确的范围 "from X to Y"
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
    
    # 模式2: 单月 "in June 2025" 或 "trend in March"
    # 优先匹配完整月份名
    for name, idx in _MONTHS.items():
        if re.search(rf"\bin\s+{name}\b", t):
            # 查找年份
            yy = re.search(r"\b(20\d{2})\b", t)
            y = int(yy.group(1)) if yy else None
            return idx, idx, y  # start=end 表示单月
    
    # 匹配缩写月份
    for abbr, idx in _MONTH_ABBR.items():
        if re.search(rf"\bin\s+{abbr}\b", t):
            yy = re.search(r"\b(20\d{2})\b", t)
            y = int(yy.group(1)) if yy else None
            return idx, idx, y
    
    return None, None, None


def _parse_park(text: str) -> Optional[str]:
    """增强版公园名提取，支持更多模式"""
    t = _norm(text)
    
    # 模式1: "in XXX Park" / "at XXX Park"
    m = re.search(r"(?:in|at|for)\s+([a-z][a-z\s\-\&]+park)\b", t)
    if m:
        return m.group(1).title()
    
    # 模式2: 直接提到已知公园名（从数据中提取）
    known_parks = [
        "alice town", "cambridge", "garden", "grandview", 
        "mcgill", "mcspadden", "mosaic creek"
    ]
    for park in known_parks:
        if park in t:
            return park.title() + " Park"
    
    return None


def _detect_domain(text: str) -> str:
    """粗粒度领域判定：mowing / permit / horticulture / generic..."""
    t = _norm(text)
    if any(k in t for k in ["mowing", "mow", "turf", "grass", "lawn"]):
        return "mowing"
    return "generic"


@dataclass
class NLUResult:
    intent: str                   # SQL_tool / RAG / CV_tool / RAG+SQL_tool / RAG+CV_tool
    confidence: float
    slots: Dict[str, Any]         # month/year/park/domain/…
    template_hint: Optional[str]  # 建议的模板标识


def classify_intent_and_slots(
    text: str, image_uri: Optional[str] = None
) -> NLUResult:
    q = text.strip()
    q_emb = _ENCODER.encode([q], normalize_embeddings=True)
    sims = util.cos_sim(q_emb, _PROT_EMB).cpu().tolist()[0]

    # TOP-1 原型
    best_i = max(range(len(sims)), key=lambda i: sims[i])
    best_label = _PROT_LABELS[best_i]
    best_score = float(sims[best_i])

    # 若携带图片，强化到含 CV 的意图
    if image_uri:
        if "RAG" in best_label:
            best_label = "RAG+CV_tool"
        else:
            best_label = "CV_tool"

    # 抽取实体
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

    # -------- 模板路由建议 --------
    template_hint = None
    lowq = _norm(q)
    
    if domain == "mowing":
        # ✅ 优先级调整：先匹配最具体的模式
        
        # 1. 最高成本（优先级最高，避免被 "to" 误判）
        if any(k in lowq for k in ["highest", "top", "max", "most expensive"]) and "cost" in lowq:
            template_hint = "mowing.labor_cost_month_top1"
        
        # 2. 最近除草时间
        elif any(k in lowq for k in ["last", "recent", "latest", "when was"]) and any(k in lowq for k in ["mow", "mowing"]):
            template_hint = "mowing.last_mowing_date"
        
        # 3. 成本趋势（需要明确的关键词或范围）
        elif "trend" in lowq and "cost" in lowq:
            template_hint = "mowing.cost_trend"
        # 或明确的 "from X to Y" 模式
        elif re.search(r'\bfrom\s+\w+\s+to\s+\w+', lowq) and "cost" in lowq:
            template_hint = "mowing.cost_trend"
        
        # 4. 公园对比（单月）
        elif any(k in lowq for k in ["compare", "across", "all parks"]) and "cost" in lowq:
            template_hint = "mowing.cost_by_park_month"
        
        # 5. 详细分解
        elif any(k in lowq for k in ["breakdown", "detail", "break down"]):
            template_hint = "mowing.cost_breakdown"
        
        # 6. 兜底：按park分组
        elif "by park" in lowq or "each park" in lowq:
            template_hint = "mowing.cost_by_park_month"

    # RAG-only 的常见触发
    if any(k in lowq for k in ["steps", "procedure", "safety", "manual", "how to", "sop"]):
        if "CV_tool" not in best_label:
            best_label = "RAG"

    print(f"[NLU] Query: '{q}'")
    print(f"[NLU] Intent: {best_label} (confidence: {best_score:.3f})")
    print(f"[NLU] Slots: {slots}")
    print(f"[NLU] Template hint: {template_hint}")

    return NLUResult(
        intent=best_label,
        confidence=round(best_score, 3),
        slots=slots,
        template_hint=template_hint,
    )


def build_route_plan(nlu_result: NLUResult) -> List[Dict[str, Any]]:
    """根据 NLU 结果构建工具调用计划"""
    plan: List[Dict[str, Any]] = []
    intent = nlu_result.intent
    slots = nlu_result.slots
    template_hint = nlu_result.template_hint

    if intent == "RAG":
        # 纯 RAG 查询：检索文档 + 提取 SOP
        plan.append({
            "tool": "kb_retrieve",
            "args": {
                "query": "mowing standard safety equipment frequency lane kilometer pricing",
                "top_k": 5
            }
        })
        plan.append({
            "tool": "sop_extract",
            "args": {
                "schema": ["steps", "materials", "tools", "safety"]
            }
        })
        print(f"[NLU] Plan: RAG workflow (kb_retrieve + sop_extract)")

    elif intent == "SQL_tool":
        # 纯 SQL 查询
        template = template_hint or "mowing.labor_cost_month_top1"  # 默认模板
        
        # 根据模板类型构建参数
        params = {
            "month": slots.get("month"),
            "year": slots.get("year"),
            "park_name": slots.get("park_name"),
        }
        
        # 如果是趋势查询，添加范围参数
        if template == "mowing.cost_trend":
            # 优先使用 range_year
            params["year"] = slots.get("range_year") or slots.get("year")
            params["start_month"] = slots.get("start_month") or slots.get("month") or 1
            params["end_month"] = slots.get("end_month") or slots.get("month") or 12
            # 移除单月参数
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
        # RAG + SQL 混合
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
        # 纯 CV 评估
        plan.append({
            "tool": "cv_assess_rag",
            "args": {
                "image_uri": slots.get("image_uri"),
                "topic_hint": "turf wear disease inspection guidelines"
            }
        })
        print(f"[NLU] Plan: CV workflow (cv_assess_rag)")

    elif intent == "RAG+CV_tool":
        # RAG + CV 混合
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
    主入口函数：解析用户输入，返回意图、槽位和执行计划
    
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
    plan = build_route_plan(nlu_result)
    
    # 生成澄清问题
    clarifications = []
    if nlu_result.intent in ["SQL_tool", "RAG+SQL_tool"]:
        template = nlu_result.template_hint
        
        # 趋势查询需要月份范围
        if template == "mowing.cost_trend":
            if not nlu_result.slots.get("start_month") or not nlu_result.slots.get("end_month"):
                clarifications.append("Which time period would you like to see? (e.g., from January to June)")
        
        # 其他查询需要月份/年份
        elif template in ["mowing.cost_by_park_month", "mowing.cost_breakdown", "mowing.labor_cost_month_top1"]:
            if not nlu_result.slots.get("month") or not nlu_result.slots.get("year"):
                clarifications.append("Which month and year would you like to query?")
        
        # 最近除草时间可以不需要时间参数，但需要公园名更准确
        elif template == "mowing.last_mowing_date":
            if not nlu_result.slots.get("park_name"):
                clarifications.append("Which park would you like to check? (or say 'all parks')")
    
    return {
        "intent": nlu_result.intent,
        "confidence": nlu_result.confidence,
        "slots": nlu_result.slots,
        "route_plan": plan,
        "clarifications": clarifications
    }