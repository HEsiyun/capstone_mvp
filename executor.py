from __future__ import annotations
import time
from typing import Any, Dict, List

from rag import kb_retrieve, sop_extract
from sql_tool import sql_query_rag
from cv_tool import cv_assess_rag

TOOL_REGISTRY = {
    "kb_retrieve": kb_retrieve,
    "sop_extract": sop_extract,
    "sql_query_rag": sql_query_rag,
    "cv_assess_rag": cv_assess_rag,
}

def execute_plan(plan: List[Dict[str, Any]], slots: Dict[str, Any]) -> Dict[str, Any]:
    state = {
        "slots": slots,
        "plan": plan,
        "evidence": {"kb_hits": [], "sop": {}, "sql": {}, "cv": {}, "support": []},
        "logs": [],
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
            elif tool == "sql_query_rag":
                out = TOOL_REGISTRY[tool](**args)
                state["evidence"]["sql"] = {k: v for k, v in out.items() if k in ("rows", "rowcount", "elapsed_ms")}
                state["evidence"]["support"] = out.get("support", [])
            elif tool == "cv_assess_rag":
                out = TOOL_REGISTRY[tool](**args)
                state["evidence"]["cv"] = out.get("cv", {})
                state["evidence"]["support"] = out.get("support", [])
            else:
                out = {"_warn": f"Unknown tool {tool}"}
            ok, err = True, None
        except Exception as e:
            ok, err = False, str(e)
            out = {"error": err}
        state["logs"].append({
            "tool": tool, "args_redacted": list(args.keys()),
            "elapsed_ms": int((time.time() - t0) * 1000),
            "ok": ok, "err": err,
        })
    return state