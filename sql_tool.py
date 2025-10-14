# sql_tool.py
from __future__ import annotations
import os, time
from datetime import datetime
from typing import Any, Dict, Callable

import duckdb, pandas as pd

# -----------------------------
# Config (adjust paths as needed)
# -----------------------------
DATA_DIR = os.path.abspath("data")
DUCK_FILE = os.path.join(DATA_DIR, "mowing.duckdb")
LABOR_XLSX = os.path.join(DATA_DIR, "6 Mowing Reports to Jun 20 2025.xlsx")
LABOR_SHEET = 0  # or sheet name string

# -----------------------------
# DuckDB bootstrap
# -----------------------------
def _ensure_duck() -> duckdb.DuckDBPyConnection:
    """Create a DuckDB connection and load the latest Excel into a table."""
    con = duckdb.connect(DUCK_FILE)

    # Read Excel fresh (simple & explicit for MVP)
    df = pd.read_excel(LABOR_XLSX, sheet_name=LABOR_SHEET)
    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]

    # Parse dates robustly (avoid out-of-bounds errors)
    if "Posting Date" in df.columns:
        # try a fast path, then a tolerant path
        try:
            df["Posting Date"] = pd.to_datetime(df["Posting Date"], format="%m/%d/%y", errors="coerce")
        except Exception:
            pass
        df["Posting Date"] = pd.to_datetime(df["Posting Date"], errors="coerce")
        df = df.dropna(subset=["Posting Date"])

    # Ensure numeric cost
    if "Val.in rep.cur." in df.columns:
        df["Val.in rep.cur."] = pd.to_numeric(df["Val.in rep.cur."], errors="coerce").fillna(0.0)

    # Re-create table
    con.execute("DROP TABLE IF EXISTS labor_data")
    con.register("labor_df", df)
    con.execute("CREATE TABLE labor_data AS SELECT * FROM labor_df")
    return con

# -----------------------------
# Template implementations
# -----------------------------
def _tpl_mowing_labor_cost_month_top1(con: duckdb.DuckDBPyConnection, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns the park with the highest total mowing labor cost in the given month/year.
    Expects params: { "month": int (1-12), "year": int }
    """
    month = params.get("month")
    year = params.get("year")

    # Validate defaults if missing
    if not isinstance(month, int) or month < 1 or month > 12:
        month = datetime.utcnow().month
    if not isinstance(year, int) or year < 2000 or year > 2100:
        year = datetime.utcnow().year

    sql = f"""
    WITH month_data AS (
      SELECT
        "CO Object Name" AS park,
        CAST("Val.in rep.cur." AS DOUBLE) AS cost,
        "Posting Date"::TIMESTAMP AS posting_dt
      FROM labor_data
    )
    SELECT park, SUM(cost) AS total_cost
    FROM month_data
    WHERE year(posting_dt) = {year}
      AND month(posting_dt) = {month}
    GROUP BY park
    ORDER BY total_cost DESC
    LIMIT 1;
    """
    t0 = time.time()
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    elapsed = int((time.time() - t0) * 1000)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": elapsed}


def _tpl_mowing_last_date_by_park(con: duckdb.DuckDBPyConnection, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns the most recent mowing date for a specific park or all parks.
    Expects params: { "park_name": str (optional) }
    
    Example queries:
    - "When was the last mowing at Cambridge Park?"
    - "Show me the most recent mowing date for each park"
    """
    park_name = params.get("park_name")
    
    if park_name:
        # Specific park query
        sql = f"""
        SELECT 
            "CO Object Name" AS park,
            MAX("Posting Date") AS last_mowing_date,
            COUNT(*) AS total_mowing_sessions,
            SUM(CAST("Val.in rep.cur." AS DOUBLE)) AS total_cost
        FROM labor_data
        WHERE LOWER("CO Object Name") LIKE LOWER('%{park_name}%')
        GROUP BY "CO Object Name"
        ORDER BY last_mowing_date DESC
        LIMIT 1;
        """
    else:
        # All parks query
        sql = """
        SELECT 
            "CO Object Name" AS park,
            MAX("Posting Date") AS last_mowing_date,
            COUNT(*) AS total_sessions,
            SUM(CAST("Val.in rep.cur." AS DOUBLE)) AS total_cost
        FROM labor_data
        GROUP BY "CO Object Name"
        ORDER BY last_mowing_date DESC;
        """
    
    t0 = time.time()
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    elapsed = int((time.time() - t0) * 1000)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": elapsed}


def _tpl_mowing_cost_trend(con: duckdb.DuckDBPyConnection, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns monthly mowing cost trend for a date range.
    Expects params: { 
        "start_month": int (1-12), 
        "end_month": int (1-12), 
        "year": int,
        "park_name": str (optional - for specific park trend)
    }
    
    Example queries:
    - "Show mowing cost trend from January to June 2025"
    - "How did costs change from April to June 2025 for Cambridge Park?"
    """
    start_month = params.get("start_month")
    end_month = params.get("end_month")
    year = params.get("year") or params.get("range_year")
    park_name = params.get("park_name")
    
    # Defaults
    if not isinstance(year, int) or year < 2000:
        year = datetime.utcnow().year
    if not isinstance(start_month, int) or start_month < 1 or start_month > 12:
        start_month = 1
    if not isinstance(end_month, int) or end_month < 1 or end_month > 12:
        end_month = 12
    
    # Build WHERE clause for park filter
    park_filter = ""
    if park_name:
        park_filter = f"AND LOWER(\"CO Object Name\") LIKE LOWER('%{park_name}%')"
    
    sql = f"""
    WITH monthly_costs AS (
        SELECT 
            year("Posting Date") AS year,
            month("Posting Date") AS month,
            "CO Object Name" AS park,
            SUM(CAST("Val.in rep.cur." AS DOUBLE)) AS monthly_cost,
            COUNT(*) AS session_count
        FROM labor_data
        WHERE year("Posting Date") = {year}
          AND month("Posting Date") BETWEEN {start_month} AND {end_month}
          {park_filter}
        GROUP BY year("Posting Date"), month("Posting Date"), "CO Object Name"
    )
    SELECT 
        year,
        month,
        park,
        monthly_cost,
        session_count
    FROM monthly_costs
    ORDER BY year, month, park;
    """
    
    t0 = time.time()
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    elapsed = int((time.time() - t0) * 1000)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": elapsed, "chart_type": "line"}


def _tpl_mowing_cost_by_park_month(con: duckdb.DuckDBPyConnection, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns cost comparison across all parks for a specific month.
    Expects params: { "month": int (1-12), "year": int }
    
    Example queries:
    - "Compare mowing costs across all parks in March 2025"
    - "Show total mowing costs breakdown by park in April"
    """
    month = params.get("month")
    year = params.get("year")
    
    # Defaults
    if not isinstance(month, int) or month < 1 or month > 12:
        month = datetime.utcnow().month
    if not isinstance(year, int) or year < 2000 or year > 2100:
        year = datetime.utcnow().year
    
    sql = f"""
    SELECT 
        "CO Object Name" AS park,
        SUM(CAST("Val.in rep.cur." AS DOUBLE)) AS total_cost,
        COUNT(*) AS mowing_sessions,
        AVG(CAST("Val.in rep.cur." AS DOUBLE)) AS avg_cost_per_session,
        SUM("Total quantity") AS total_quantity
    FROM labor_data
    WHERE year("Posting Date") = {year}
      AND month("Posting Date") = {month}
    GROUP BY "CO Object Name"
    ORDER BY total_cost DESC;
    """
    
    t0 = time.time()
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    elapsed = int((time.time() - t0) * 1000)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": elapsed, "chart_type": "bar"}


def _tpl_mowing_cost_breakdown_by_park(con: duckdb.DuckDBPyConnection, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns detailed monthly cost breakdown for a specific park or all parks.
    Expects params: { 
        "park_name": str (optional),
        "month": int (optional - if not provided, shows all months),
        "year": int
    }
    
    Example queries:
    - "Show total mowing costs breakdown by park in March 2025"
    - "What's the cost breakdown for Cambridge Park?"
    """
    park_name = params.get("park_name")
    month = params.get("month")
    year = params.get("year")
    
    # Defaults
    if not isinstance(year, int) or year < 2000 or year > 2100:
        year = datetime.utcnow().year
    
    # Build WHERE clause
    where_parts = [f"year(\"Posting Date\") = {year}"]
    
    if park_name:
        where_parts.append(f"LOWER(\"CO Object Name\") LIKE LOWER('%{park_name}%')")
    
    if isinstance(month, int) and 1 <= month <= 12:
        where_parts.append(f"month(\"Posting Date\") = {month}")
    
    where_clause = " AND ".join(where_parts)
    
    sql = f"""
    SELECT 
        "CO Object Name" AS park,
        month("Posting Date") AS month,
        "ParActivity" AS activity_type,
        SUM(CAST("Val.in rep.cur." AS DOUBLE)) AS cost,
        COUNT(*) AS sessions,
        SUM("Total quantity") AS total_quantity
    FROM labor_data
    WHERE {where_clause}
    GROUP BY "CO Object Name", month("Posting Date"), "ParActivity"
    ORDER BY park, month, cost DESC;
    """
    
    t0 = time.time()
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    elapsed = int((time.time() - t0) * 1000)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": elapsed}


# -----------------------------
# Dispatcher registry
# -----------------------------
TEMPLATE_REGISTRY: Dict[str, Callable[[duckdb.DuckDBPyConnection, Dict[str, Any]], Dict[str, Any]]] = {
    # Original template
    "mowing.labor_cost_month_top1": _tpl_mowing_labor_cost_month_top1,
    
    # NEW: 最近除草时间
    "mowing.last_mowing_date": _tpl_mowing_last_date_by_park,
    
    # NEW: 成本趋势图
    "mowing.cost_trend": _tpl_mowing_cost_trend,
    
    # NEW: 公园对比（单月）
    "mowing.cost_by_park_month": _tpl_mowing_cost_by_park_month,
    
    # NEW: 月度总览（详细分解）
    "mowing.cost_breakdown": _tpl_mowing_cost_breakdown_by_park,
}

# -----------------------------
# Public entry point
# -----------------------------
def run_sql_template(template: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified SQL template executor.
    Usage: run_sql_template("mowing.labor_cost_month_top1", {"month": 3, "year": 2025})
    Returns: {"rows": [...], "rowcount": int, "elapsed_ms": int}
    """
    if template not in TEMPLATE_REGISTRY:
        return {
            "rows": [{"error": f"Unknown SQL template: {template}"}],
            "rowcount": 1,
            "elapsed_ms": 0,
        }

    con = _ensure_duck()
    try:
        func = TEMPLATE_REGISTRY[template]
        out = func(con, params or {})
        return out
    finally:
        try:
            con.close()
        except Exception:
            pass

# -----------------------------
# RAG-compatible wrapper (for executor.py)
# -----------------------------
def sql_query_rag(template: str = None, params: Dict[str, Any] = None, 
                  support: list = None, **kwargs) -> Dict[str, Any]:
    """
    Wrapper for RAG executor compatibility.
    
    Args:
        template: SQL template name (e.g., "mowing.labor_cost_month_top1")
        params: Template parameters
        support: Optional support documents (for future use)
        **kwargs: Additional arguments (merged into params)
    
    Returns:
        Dict with keys: rows, rowcount, elapsed_ms, support
    """
    # Merge kwargs into params
    if params is None:
        params = {}
    params.update(kwargs)
    
    # Default template if not specified
    if template is None:
        template = "mowing.labor_cost_month_top1"
    
    # Run the template
    result = run_sql_template(template, params)
    
    # Add support field for RAG compatibility
    result["support"] = support or []
    
    return result


# ✅ 最近除草时间
"When was the last mowing at Cambridge Park?"
"Show me the most recent mowing date for each park"

# ✅ 成本趋势
"Show mowing cost trend from January to June 2025"
"How did costs change from April to June for Garden Park?"

# ✅ 公园对比
"Compare mowing costs across all parks in March 2025"
"Show me all parks ranked by mowing cost in April"

# ✅ 详细分解
"Show total mowing costs breakdown by park in March 2025"
"What's the cost breakdown for Cambridge Park?"

# ✅ 原有功能
"Which park had the highest mowing cost in March 2025?"
"What are the mowing safety requirements?"