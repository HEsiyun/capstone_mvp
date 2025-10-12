from __future__ import annotations
import os

# ---- Paths ----
DATA_DIR = os.path.abspath("data")
RAG_DOC_DIR = os.path.join(DATA_DIR, "rag_docs")
FAISS_DIR   = os.path.join(DATA_DIR, "faiss_index")
os.makedirs(RAG_DOC_DIR, exist_ok=True)
os.makedirs(FAISS_DIR,   exist_ok=True)

# ---- DuckDB demo input ----
DUCK_FILE    = os.path.join(DATA_DIR, "mowing.duckdb")
LABOR_XLSX   = os.path.join(DATA_DIR, "6 Mowing Reports to Jun 20 2025.xlsx")
LABOR_SHEET  = 0  # or a sheet name like "Sheet1"

# ---- Optional numpy check (for FAISS embeddings) ----
try:
    import numpy as _np  # noqa: F401
    NUMPY_AVAILABLE = True
except Exception:
    NUMPY_AVAILABLE = False