from __future__ import annotations
import time
from datetime import datetime
from typing import Any, Dict, Optional

import duckdb, pandas as pd
from config import DUCK_FILE, LABOR_XLSX, LABOR_SHEET
from rag import RAG

def _ensure_duck():
    con = duckdb.connect(DUCK_FILE)
    df = pd.read_excel(LABOR_XLSX, sheet_name=LABOR_SHEET)
    df.columns = [str(c).strip() for c in df.columns]

    if "Posting Date" in df.columns:
        try:
            df["Posting Date"] = pd.to_datetime(df["Posting Date"], format="%m/%d/%y", errors="coerce")
        except Exception:
            pass
        df["Posting Date"] = pd.to_datetime(df["Posting Date"], errors="coerce")
        df = df.dropna(subset=["Posting Date"])

    if "Val.in rep.cur." in df.columns:
        df["Val.in rep.cur."] = pd.to_numeric(df["Val.in rep.cur."], errors="coerce").fillna(0.0)

    con.execute("DROP TABLE IF EXISTS labor_data")
    con.register("labor_df", df)
    con.execute("CREATE TABLE labor_data AS SELECT * FROM labor_df")
    return con

def sql_query_rag(template: str, params: Dict[str, Any], qctx: Optional[str] = None):
    con = _ensure_duck()
    month = params.get("month")
    year  = params.get("year")

    if not isinstance(month, int) or month < 1 or month > 12:
        month = datetime.utcnow().month
    if not isinstance(year, int) or year < 2000 or year > 2100:
        year = datetime.utcnow().year

    if template == "labor_cost_month_top1":
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
    else:
        sql = "SELECT 'unknown template' AS msg;"

    t0 = time.time()
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    elapsed = int((time.time()-t0)*1000)
    con.close()

    support = RAG.retrieve(qctx or "mowing labor cost pricing frequency lane kilometer hourly rate standard", k=3)
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": elapsed, "support": support}