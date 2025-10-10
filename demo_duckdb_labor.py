# 1️⃣ Which park had the highest total mowing labor cost in May 2025?

import duckdb, pandas as pd
from pathlib import Path

excel_path = Path("data/6 Mowing Reports to Jun 20 2025.xlsx")
df = pd.read_excel(excel_path, sheet_name=0)

# Normalize types
df["Posting Date"] = pd.to_datetime(df["Posting Date"], errors="coerce")
df["Val.in rep.cur."] = pd.to_numeric(df["Val.in rep.cur."], errors="coerce")

con = duckdb.connect(database=":memory:")
con.register("labor_data", df)

year, month = 2025, 5
sql = f"""
WITH month_data AS (
  SELECT
    "CO Object Name" AS park,
    "Val.in rep.cur."::DOUBLE AS cost,
    "Posting Date"::TIMESTAMP AS posting_ts
  FROM labor_data
)
SELECT park, SUM(cost) AS total_cost
FROM month_data
WHERE EXTRACT(YEAR  FROM posting_ts) = {year}
  AND EXTRACT(MONTH FROM posting_ts) = {month}
GROUP BY park
ORDER BY total_cost DESC
LIMIT 1;
"""
print(sql)
print(con.execute(sql).fetchdf())