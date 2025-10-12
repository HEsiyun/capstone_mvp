from __future__ import annotations
from typing import Any, Dict, List

def compose_answer(nlu: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    intent = nlu.get("intent")
    ev = state["evidence"]

    def _snip(txt: str, n: int = 260) -> str:
        import re as _re
        s = _re.sub(r"\s+", " ", (txt or "")).strip()
        return (s[:n] + "…") if len(s) > n else s

    answer_md = ""
    tables: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []

    if intent == "SOP_QUERY":
        sop = ev["sop"]
        answer_md = (
            f"**Mowing SOP (prototype)**\n\n"
            "### Steps\n" + "\n".join([f"{i+1}. {s}" for i, s in enumerate(sop.get('steps', []))]) +
            ("\n\n### Materials\n- " + "\n- ".join(sop.get("materials", [])) if sop.get("materials") else "") +
            ("\n\n### Tools\n- " + "\n- ".join(sop.get("tools", [])) if sop.get("tools") else "") +
            ("\n\n### Safety\n- " + "\n- ".join(sop.get("safety", [])) if sop.get("safety") else "")
        )
        sup = ev.get("kb_hits", [])
        if sup:
            answer_md += "\n\n### Context snippets\n" + "\n".join(
                [f"- {_snip(h.get('text',''))} _(p.{h.get('page','?')})_" for h in sup[:3]]
            )
        for h in sup:
            citations.append({"title": "Standard/Manual", "source": h["source"]})

    elif intent == "DATA_QUERY":
        sql = ev["sql"]
        rows = sql.get("rows", [])
        tables.append({
            "name": "Top park by mowing labor cost (selected month)",
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
        })
        answer_md = (
            f"**Query Result**\n\n"
            f"Returned **{sql.get('rowcount',0)}** rows in **{sql.get('elapsed_ms',0)}ms**."
        )
        sup = ev.get("support", [])
        if sup:
            answer_md += "\n\n### Context snippets\n" + "\n".join(
                [f"- {_snip(h.get('text',''))} _(p.{h.get('page','?')})_" for h in sup[:3]]
            )
        for h in sup:
            citations.append({"title": "Mowing standard (RAG)", "source": h["source"]})

    elif intent == "IMAGE_ASSESS":
        cv = ev["cv"]
        answer_md = (
            f"**Image Assessment (mock + RAG)**\n\n"
            f"Condition: **{cv.get('condition','unknown')}** (score {cv.get('score',0):.2f})\n\n"
            f"Labels: {', '.join(cv.get('labels', []))}\n\n"
            f"Notes: {'; '.join(cv.get('explanations', []))}"
        )
        sup = ev.get("support", [])
        if sup:
            answer_md += "\n\n### Context snippets\n" + "\n".join(
                [f"- {_snip(h.get('text',''))} _(p.{h.get('page','?')})_" for h in sup[:3]]
            )
        for h in sup:
            citations.append({"title": "Inspection guidance (RAG)", "source": h["source"]})
        if cv.get("low_confidence"):
            answer_md = "> ⚠ Low confidence — consider another angle.\n\n" + answer_md

    else:
        answer_md = "I couldn't map this to a known workflow."

    return {"answer_md": answer_md, "tables": tables, "map_layer": None,
            "citations": citations, "logs": state["logs"]}