from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

from rag import kb_retrieve, sop_extract
from sql_tool import sql_query_rag

# cv_tool import with fallback
try:
    from cv_tool import cv_assess_rag
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False
    print("[WARN] cv_tool not available, cv_assess_rag will be disabled")

# Build tool registry dynamically
TOOL_REGISTRY = {
    "kb_retrieve": kb_retrieve,
    "sop_extract": sop_extract,
    "sql_query_rag": sql_query_rag,
}

if CV_AVAILABLE:
    TOOL_REGISTRY["cv_assess_rag"] = cv_assess_rag


def execute_plan(plan: List[Dict[str, Any]], slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a list of tool calls in sequence and accumulate evidence.
    
    Args:
        plan: List of steps, each with {"tool": str, "args": dict}
        slots: User intent slots (e.g., query, month, year)
    
    Returns:
        state: Dict with slots, plan, evidence, and execution logs
    """
    state = {
        "slots": slots,
        "plan": plan,
        "evidence": {
            "kb_hits": [],
            "sop": {},
            "sql": {},
            "cv": {},
            "support": []
        },
        "logs": [],
    }
    
    for step in plan:
        tool = step["tool"]
        args = step.get("args", {}) or {}
        t0 = time.time()
        
        try:
            if tool == "kb_retrieve":
                # Retrieve documents from knowledge base
                out = TOOL_REGISTRY[tool](**args)
                state["evidence"]["kb_hits"] = out.get("hits", [])
                ok, err = True, None
                
            elif tool == "sop_extract":
                # Extract SOP structure from previously retrieved documents
                snippets = [h["text"] for h in state["evidence"]["kb_hits"]]
                
                # Add schema to args if provided in step
                if "schema" not in args:
                    args["schema"] = None
                    
                out = TOOL_REGISTRY[tool](snippets=snippets, **args)
                state["evidence"]["sop"] = out
                ok, err = True, None
                
            elif tool == "sql_query_rag":
                # Execute SQL query template
                out = TOOL_REGISTRY[tool](**args)
                
                # Store SQL results
                state["evidence"]["sql"] = {
                    k: v for k, v in out.items() 
                    if k in ("rows", "rowcount", "elapsed_ms")
                }
                
                # Update support documents
                if "support" in out:
                    state["evidence"]["support"] = out["support"]
                    
                ok, err = True, None
                
            elif tool == "cv_assess_rag":
                # Computer vision assessment
                if not CV_AVAILABLE:
                    out = {"error": "cv_tool not available"}
                    ok, err = False, "cv_tool not imported"
                else:
                    out = TOOL_REGISTRY[tool](**args)
                    
                    # Store CV results
                    if "cv" in out:
                        state["evidence"]["cv"] = out["cv"]
                    
                    # Update support documents
                    if "support" in out:
                        state["evidence"]["support"] = out["support"]
                        
                    ok, err = True, None
                    
            else:
                # Unknown tool
                out = {"_warn": f"Unknown tool: {tool}"}
                ok, err = False, f"Unknown tool: {tool}"
                
        except Exception as e:
            # Handle any execution errors
            ok, err = False, str(e)
            out = {"error": err}
            print(f"[ERROR] Tool '{tool}' failed: {err}")
        
        # Log this step's execution
        elapsed_ms = int((time.time() - t0) * 1000)
        state["logs"].append({
            "tool": tool,
            "args_redacted": list(args.keys()),
            "elapsed_ms": elapsed_ms,
            "ok": ok,
            "err": err,
        })
    
    return state