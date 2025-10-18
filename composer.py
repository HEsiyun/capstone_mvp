# composer.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import re

# ========== LLM Integration (Ollama Only) ==========
# This system uses OLLAMA for local LLM inference
# No OpenAI API key required - all processing is local
# 
# Prerequisites:
# 1. Install Ollama: brew install ollama (or from https://ollama.com)
# 2. Start Ollama: open -a Ollama
# 3. Download model: ollama pull llama3.2:3b
# 4. Install Python client: pip install openai
#
# The 'openai' package is only used as a client library to connect
# to Ollama's OpenAI-compatible API endpoint (http://localhost:11434/v1)

try:
    from openai import OpenAI
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("[WARN] OpenAI library not available. Install: pip install openai")
    print("[INFO] Note: We use OpenAI library to connect to Ollama (local LLM)")

# Configuration - Local Ollama Only
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "llama3.2:3b"  # Available models: llama3.2:3b, llama3.2:1b, mistral, phi3

# To switch models, change OLLAMA_MODEL and ensure the model is downloaded:
# ollama pull llama3.2:1b  (faster, smaller)
# ollama pull mistral      (more capable, slower)
# ollama pull phi3         (Microsoft, good balance)


def _summarize_rag_context(
    rag_snippets: List[Dict[str, Any]], 
    query: str,
    sql_result_summary: str = ""
) -> str:
    """
    Use local Ollama LLM to summarize RAG document snippets into coherent context
    
    Note: This uses Ollama (local LLM), NOT OpenAI API
    We use the 'openai' Python library only as a client to connect to Ollama's OpenAI-compatible API
    
    Args:
        rag_snippets: RAG retrieved document snippets
        query: User's original query
        sql_result_summary: SQL query result summary (if available)
    
    Returns:
        Formatted context explanation
    """
    if not LLM_AVAILABLE or not rag_snippets:
        # Fallback: simple formatting without LLM
        return _format_rag_snippets_simple(rag_snippets)
    
    try:
        # 准备上下文
        context_text = "\n\n".join([
            f"Source {i+1} (page {snippet.get('page', '?')}): {snippet.get('text', '')[:500]}"
            for i, snippet in enumerate(rag_snippets[:3])
        ])
        
        # 构建 prompt
        if sql_result_summary:
            prompt = f"""You are an assistant helping interpret park maintenance data.

User Question: {query}

SQL Query Result: {sql_result_summary}

Reference Documents:
{context_text}

Task: Based on the reference documents, provide 2-3 sentences of relevant context that helps interpret the SQL results above. Focus on:
- Relevant standards, procedures, or guidelines
- Cost factors or typical ranges mentioned
- Any important notes about the data

Keep it concise and directly relevant to the user's question. Use markdown formatting."""
        else:
            prompt = f"""You are an assistant helping answer questions about park maintenance procedures.

User Question: {query}

Reference Documents:
{context_text}

Task: Summarize the key information from the reference documents that answers the user's question. Provide:
- 2-3 key points or steps
- Relevant standards or guidelines
- Important safety notes if applicable

Use markdown formatting with bullet points."""

        # Call Ollama LLM
        client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
        
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes technical documentation clearly and concisely."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300,
            timeout=10.0  # 10 second timeout
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
        
    except Exception as e:
        print(f"[WARN] Ollama LLM summarization failed: {e}")
        print(f"[INFO] Make sure Ollama is running: open -a Ollama")
        print(f"[INFO] Check model is available: ollama list")
        # Fallback to simple formatting
        return _format_rag_snippets_simple(rag_snippets)


def _format_rag_snippets_simple(snippets: List[Dict[str, Any]]) -> str:
    """
    Simple RAG snippet formatting (fallback when Ollama is unavailable)
    """
    if not snippets:
        return ""
    
    output = "### Reference Context\n\n"
    for i, snippet in enumerate(snippets[:3], 1):
        text = snippet.get("text", "")
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        text = text[:200] + "..." if len(text) > 200 else text
        
        page = snippet.get("page", "?")
        output += f"**Source {i}** (page {page}):\n{text}\n\n"
    
    return output


def _snip(txt: str, n: int = 150) -> str:
    """Truncate text and clean whitespace"""
    s = re.sub(r"\s+", " ", (txt or "")).strip()
    return (s[:n] + "...") if len(s) > n else s


def compose_answer(nlu: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    intent = nlu.get("intent", "")
    ev = state["evidence"]
    tables: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    charts: List[Dict[str, Any]] = []
    answer_md = ""
    
    # Get user's original query
    user_query = nlu.get("slots", {}).get("original_query", "")
    if not user_query and state.get("slots"):
        user_query = state["slots"].get("text", "")

    # ========== RAG content handling ==========
    if intent in ("RAG", "RAG+SQL_tool"):
        sop = ev.get("sop", {})
        kb_hits = ev.get("kb_hits", [])
        
        # Check if SOP extraction found anything useful
        has_sop_content = any(sop.get(k) for k in ["steps", "materials", "tools", "safety"])
        
        # Detect if this is actually mowing SOP or field dimensions
        is_mowing_query = False
        if kb_hits:
            # Check if retrieved documents are about mowing
            combined_text = " ".join([h.get("text", "")[:200] for h in kb_hits[:2]]).lower()
            is_mowing_query = any(k in combined_text for k in ["mowing", "mow", "contractor", "equipment", "ppe"])
        
        if has_sop_content and is_mowing_query:
            # Display as Mowing SOP
            answer_md = (
                "**Mowing SOP (Standard Operating Procedures)**\n\n"
                "### Steps\n" + "\n".join([f"{i+1}. {s}" for i, s in enumerate(sop.get("steps", []))]) +
                ( "\n\n### Materials\n- " + "\n- ".join(sop.get("materials", [])) if sop.get("materials") else "" ) +
                ( "\n\n### Tools\n- " + "\n- ".join(sop.get("tools", [])) if sop.get("tools") else "" ) +
                ( "\n\n### Safety\n- " + "\n- ".join(sop.get("safety", [])) if sop.get("safety") else "" )
            )
            
            for h in kb_hits[:3]:
                citations.append({"title": "Mowing Standard/Manual", "source": h.get("source", "")})
                
        elif kb_hits:
            # Field dimensions or other RAG query - use LLM to summarize
            answer_md = "### Field Standards Information\n\n"
            
            # Use LLM to summarize RAG hits
            if LLM_AVAILABLE:
                try:
                    summary = _summarize_rag_context(
                        rag_snippets=kb_hits,
                        query=user_query or "Field standards query",
                        sql_result_summary=""
                    )
                    answer_md += summary
                except Exception as e:
                    print(f"[WARN] LLM summary failed, using fallback: {e}")
                    answer_md += _format_rag_snippets_simple(kb_hits)
            else:
                # Fallback: show formatted snippets
                answer_md += _format_rag_snippets_simple(kb_hits)
            
            for h in kb_hits[:3]:
                citations.append({"title": "Field Standards Reference", "source": h.get("source", "")})

    # ========== SQL content handling + chart generation ==========
    if intent in ("SQL_tool", "RAG+SQL_tool"):
        sql = ev.get("sql", {})
        rows = sql.get("rows", [])
        
        # Get template hint
        template_hint = None
        if state.get("plan"):
            for step in state["plan"]:
                if step.get("tool") == "sql_query_rag":
                    template_hint = step.get("args", {}).get("template")
                    break
        
        # Generate chart config
        chart_config = _detect_chart_type(rows, template_hint)
        if chart_config:
            charts.append(chart_config)
            chart_desc = _generate_chart_description(chart_config, rows)
            if chart_desc:
                if answer_md:
                    answer_md += "\n\n"
                answer_md += chart_desc + "\n\n"
        
        # Table data
        tables.append({
            "name": _get_table_name(template_hint, nlu.get("slots", {})),
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows
        })
        
        # Generate SQL result summary
        sql_summary = _generate_sql_summary(rows, template_hint, nlu.get("slots", {}))
        
        if answer_md:
            answer_md += "\n\n"
        
        # Main results
        answer_md += sql_summary
        answer_md += f"\n\n**Query Performance**: {sql.get('rowcount',0)} rows in {sql.get('elapsed_ms',0)}ms"
        
        # KEY FEATURE: Use Ollama LLM to enhance RAG content
        if intent == "RAG+SQL_tool":
            rag_hits = ev.get("kb_hits", [])
            if rag_hits:
                answer_md += "\n\n---\n\n"
                # Use Ollama to summarize RAG context
                rag_context = _summarize_rag_context(
                    rag_snippets=rag_hits,
                    query=user_query,
                    sql_result_summary=sql_summary
                )
                answer_md += rag_context
                
                # Add citations
                for h in rag_hits[:3]:
                    citations.append({
                        "title": "Reference Document", 
                        "source": h.get("source", "")
                    })

    # ========== CV content handling ==========
    if intent in ("CV_tool", "RAG+CV_tool"):
        cv = ev.get("cv", {})
        
        # Check if this is mock data
        is_mock = any("VLM not configured" in str(label) for label in cv.get("labels", []))
        
        if answer_md:
            answer_md += "\n\n"
        
        if is_mock:
            # Mock assessment - show helpful setup message
            answer_md += (
                "**Image Analysis (Not Configured)**\n\n"
                "To enable AI-powered image analysis:\n"
                "1. Get free API key from https://openrouter.ai/\n"
                "2. Set environment variable: `export OPENROUTER_API_KEY='your-key'`\n"
                "3. Restart backend\n\n"
                "Supported analysis:\n"
                "- Field condition assessment\n"
                "- Turf health evaluation\n"
                "- Maintenance recommendations\n"
                "- Safety hazard detection"
            )
        else:
            # Real VLM assessment
            answer_md += (
                "**Image Assessment**\n\n"
                f"Condition: **{cv.get('condition','unknown')}** (score {cv.get('score',0):.2f})\n\n"
                f"Issues: {', '.join(cv.get('labels', []))}\n\n"
                f"Recommendations: {'; '.join(cv.get('explanations', []))}"
            )
            
            if cv.get("low_confidence"):
                answer_md = "> ⚠️ Low confidence - consider uploading a clearer image.\n\n" + answer_md
        
        # RAG context (if available)
        if intent == "RAG+CV_tool":
            rag_hits = ev.get("kb_hits", [])
            if rag_hits and not is_mock:
                answer_md += "\n\n---\n\n"
                rag_context = _summarize_rag_context(
                    rag_snippets=rag_hits,
                    query=user_query,
                    sql_result_summary=""
                )
                answer_md += rag_context
        
        for h in ev.get("support", [])[:2]:
            citations.append({"title": "Reference Standards", "source": h.get("source", "")})

    # ========== Fallback ==========
    if not answer_md:
        answer_md = "I couldn't generate a response for this query."

    return {
        "answer_md": answer_md,
        "tables": tables,
        "charts": charts,
        "map_layer": None,
        "citations": citations,
        "logs": state["logs"]
    }


# ========== 辅助函数 ==========

def _get_table_name(template_hint: str, slots: Dict[str, Any]) -> str:
    """Generate table name based on template"""
    if template_hint == "mowing.labor_cost_month_top1":
        month = slots.get("month", "")
        year = slots.get("year", "")
        return f"Top Park by Mowing Cost ({month}/{year})"
    elif template_hint == "mowing.cost_trend":
        return "Mowing Cost Trend"
    elif template_hint == "mowing.cost_by_park_month":
        return "Cost Comparison by Park"
    elif template_hint == "mowing.last_mowing_date":
        return "Last Mowing Dates"
    elif template_hint == "mowing.cost_breakdown":
        return "Detailed Cost Breakdown"
    return "Query Result"


def _generate_sql_summary(rows: List[Dict], template_hint: str, slots: Dict[str, Any]) -> str:
    """Generate natural language summary of SQL results"""
    if not rows:
        return "No results found."
    
    if template_hint == "mowing.labor_cost_month_top1":
        if len(rows) > 0:
            park = rows[0].get("park", "Unknown")
            cost = rows[0].get("total_cost", 0)
            month = slots.get("month", "")
            year = slots.get("year", "")
            return f"### 🏆 Results\n\n**{park}** had the highest mowing cost of **${cost:,.2f}** in {month}/{year}."
    
    elif template_hint == "mowing.cost_trend":
        return f"### 📈 Trend Analysis\n\nCost trend data across **{len(rows)} time periods**."
    
    elif template_hint == "mowing.cost_by_park_month":
        total = sum(row.get("total_cost", 0) for row in rows)
        return f"### 📊 Cost Comparison\n\n**{len(rows)} parks** with combined costs of **${total:,.2f}**."
    
    elif template_hint == "mowing.last_mowing_date":
        return f"### 📅 Last Mowing Activity\n\nShowing data for **{len(rows)} park(s)**."
    
    elif template_hint == "mowing.cost_breakdown":
        return f"### 💰 Detailed Breakdown\n\n**{len(rows)} cost entries** by activity type."
    
    return f"### Results\n\nFound **{len(rows)} records**."


def _detect_chart_type(rows: List[Dict], template_hint: str = None) -> Optional[Dict[str, Any]]:
    """Detect appropriate chart type based on data structure"""
    if not rows:
        return None
    
    columns = list(rows[0].keys())
    
    if template_hint == "mowing.cost_trend":
        if "month" in columns and "monthly_cost" in columns:
            parks = sorted(list(set(row.get("park") for row in rows if row.get("park"))))
            
            # Limit: if more than 10 parks, only show top 10 by cost
            if len(parks) > 10:
                # Calculate total cost per park
                park_totals = {}
                for park in parks:
                    park_totals[park] = sum(
                        row["monthly_cost"] for row in rows 
                        if row.get("park") == park
                    )
                # Take top 10
                top_parks = sorted(park_totals.items(), key=lambda x: x[1], reverse=True)[:10]
                parks = [p[0] for p in top_parks]
            
            return {
                "type": "line",
                "title": "Mowing Cost Trend",
                "x_axis": {"field": "month", "label": "Month", "type": "category"},
                "y_axis": {"field": "monthly_cost", "label": "Cost ($)", "type": "value"},
                "series": [
                    {
                        "name": park,
                        "data": [
                            {"x": row["month"], "y": row["monthly_cost"]}
                            for row in rows if row.get("park") == park
                        ]
                    }
                    for park in parks
                ],
                "legend": True,
                "grid": True,
                "note": f"Showing top {len(parks)} parks by total cost" if len(parks) < len(set(row.get("park") for row in rows)) else None
            }
    
    elif template_hint in ["mowing.cost_by_park_month", "mowing.labor_cost_month_top1"]:
        if "park" in columns and "total_cost" in columns:
            return {
                "type": "bar",
                "title": "Mowing Cost by Park",
                "x_axis": {"field": "park", "label": "Park", "type": "category"},
                "y_axis": {"field": "total_cost", "label": "Total Cost ($)", "type": "value"},
                "series": [
                    {
                        "name": "Total Cost",
                        "data": [{"x": row["park"], "y": row["total_cost"]} for row in rows]
                    }
                ],
                "legend": False,
                "grid": True,
                "color": "#4CAF50"
            }
    
    elif template_hint == "mowing.last_mowing_date":
        if "park" in columns or "PARK" in columns:
            # 支持大小写不敏感的字段名
            def get_field(row, *field_names):
                """尝试多个可能的字段名（大小写不敏感）"""
                for field in field_names:
                    if field in row:
                        return row[field]
                    # 尝试大写版本
                    if field.upper() in row:
                        return row[field.upper()]
                    # 尝试小写版本
                    if field.lower() in row:
                        return row[field.lower()]
                return 0
            
            return {
                "type": "timeline",
                "title": "Last Mowing Date by Park",
                "data": [
                    {
                        "park": get_field(row, "park", "PARK"),
                        "date": get_field(row, "last_mowing_date", "LAST_MOWING_DATE"),
                        "sessions": get_field(row, "total_sessions", "total_mowing_sessions", "TOTAL_SESSIONS", "TOTAL_MOWING_SESSIONS"),
                        "cost": get_field(row, "total_cost", "TOTAL_COST")
                    }
                    for row in rows
                ],
                "sort_by": "date",
                "sort_order": "desc"
            }
    
    return None


def _generate_chart_description(chart_config: Dict[str, Any], rows: List[Dict]) -> str:
    """Generate chart description text"""
    if not chart_config or not rows:
        return ""
    
    chart_type = chart_config.get("type")
    
    if chart_type == "line":
        parks = list(set(row.get("park") for row in rows if row.get("park")))
        months = sorted(set(row.get("month") for row in rows if row.get("month")))
        return f"Line chart comparing {len(parks)} park(s) from month {min(months)} to {max(months)}"
    
    elif chart_type == "bar":
        return f"Bar chart comparing {len(rows)} park(s)"
    
    elif chart_type == "timeline":
        return f"Timeline of last mowing dates for {len(rows)} park(s)"
    
    return ""