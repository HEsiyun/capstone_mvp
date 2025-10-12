Q1: 除草（planning)
SQL:割草overdue,返回好久没除草的 
RAG: planning: <2 week

Q2: labour cost合理不合理（输错了的）

# 🌿 Parks Prototype (RAG + SQL + CV Agent)

This prototype demonstrates a lightweight Retrieval-Augmented Generation (RAG) system that answers operational questions about Vancouver parks maintenance — such as mowing costs, standard operating procedures, and inspection guidance.


---

## System Components

The system combines:

* **RAG** (retrieval from PDF "mowing standards")
* **DuckDB SQL** (labor-cost aggregation from Excel)
* **Mock CV tool** (image-based inspection stub)
* **Rule-based NLU planner** → routes each question to the right tool
* **Unified FastAPI endpoint** for the frontend UI
---

## 🧩 Project Structure

```
mvp/
│
├── app.py               # FastAPI entrypoint (exposes /health, /nlu/parse, /agent/answer)
│
├── nlu.py               # Intent detection + slot extraction + route-plan builder
├── rag.py               # FAISS→BM25 retrieval index + kb_retrieve + sop_extract
├── sql_tool.py          # DuckDB SQL + RAG-assisted explanation
├── cv_tool.py           # Mock vision + RAG snippets
├── executor.py          # Tool registry + plan executor
├── composer.py          # Answer formatter (Markdown + tables + citations)
├── config.py            # Paths, filenames, and global constants
│
├── data/
│   ├── 6 Mowing Reports to Jun 20 2025.xlsx   # source for DuckDB
│   ├── rag_docs/mowing_standard.pdf           # PDF used for RAG
│   └── faiss_index/                           # persisted FAISS index
│
└── frontend/
    └── App.jsx          # simple React client (two sample queries)
```

## 🖥️ Current User Interface

![UI Screenshot](/UI.png)

## 🏗️ Setup Instructions

### 1️⃣ Create Environment
```bash
conda create -n parks-proto python=3.11
conda activate parks-proto
pip install -r requirements.txt
```
(requirements.txt includes FastAPI, Uvicorn, Pydantic, and CORS)

### 2️⃣ Run the FastAPI server:
```bash
uvicorn app:app --reload --port 8000
```
The backend will now be available at:
👉 http://127.0.0.1:8000
Endpoints:

- GET /health
- POST /nlu/parse
- POST /agent/answer
### 3️⃣ RUN Frontend (React + Vite)
```bash
# Move into frontend folder
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | quick status + which RAG mode (FAISS / BM25) |
| POST | `/nlu/parse` | returns detected intent, slots, route plan |
| POST | `/agent/answer` | full pipeline → executes plan → returns Markdown answer + table + citations |

All endpoints accept / return JSON.

`/agent/answer` can reuse an NLU parse or raw text.


## 🧠 Supported Intents

| Intent | Example question | Tools used |
|--------|------------------|------------|
| DATA_QUERY | "Which park had the highest total mowing labor cost in March 2025?" | sql_query_rag → DuckDB + RAG citations |
| SOP_QUERY | "What are the mowing steps and safety requirements?" | kb_retrieve + sop_extract |
| IMAGE_ASSESS | (upload image) | cv_assess_rag (mock CV + RAG guidelines) |

## 🧱 How It Works

1. **NLU** parses the text → detects intent → extracts month/year/park → builds a route plan.
2. **Executor** runs each tool step:
   * `sql_query_rag`: executes SQL on DuckDB, then retrieves contextual PDF snippets.
   * `kb_retrieve + sop_extract`: finds standard paragraphs and regex-extracts steps/materials/tools/safety.
   * `cv_assess_rag`: returns a mock CV assessment and related guidelines.
3. **Composer** merges results → Markdown answer + tables + citations (PDF page links + context snippets).
4. **Frontend** displays everything in a unified UI.

## 📄 Sample Questions

* Which park had the highest total mowing labor cost in March 2025?
* What are the mowing steps and safety requirements?

## 🧭 Next Steps

* Replace mock CV module with a real model or API.
* Add LLM prompt-based SOP extraction for richer results.
* Extend SQL templates (frequency, equipment costs, etc).
* Integrate multi-document RAG indexing and evaluation metrics.


---

###  Testing with Postman (Mock)可以不用

This guide explains how to test your **FastAPI backend** endpoints using **Postman**.  
You’ll be able to run both `/nlu/parse` and `/agent/answer` requests interactively,  
see example outputs, and verify that your prototype pipeline works end-to-end.

---

#### 📁 Files Overview

| File | Description |
|------|--------------|
| **`parks-prototype.postman_environment.json`** | Defines your base URL variable (`{{base_url}} = http://127.0.0.1:8000`) |
| **`parks-nlu.postman_collection.json`** | Tests the **NLU module** (`/nlu/parse`) for intent detection and slot extraction |
| **`parks-agent.postman_collection.json`** | Tests the **RAG-Agent pipeline** (`/agent/answer`) for tool execution and answer composition |

---

#### 🧩 Prerequisites

Make sure your environment is ready before running:

```bash
# Create and activate environment
conda create -n parks python=3.11 -y
conda activate parks

# Install dependencies
pip install -r requirements.txt

# Start backend
uvicorn app:app --reload --port 8000
```

If you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```
your API is ready.

---

#### 🧰 Import Collections into Postman

1. **Open Postman**  
   Download from [https://www.postman.com/downloads/](https://www.postman.com/downloads/).

2. **Import the Files**
   - Click **Import → Upload Files**
   - Select:
     - `parks-prototype.postman_environment.json`
     - `parks-nlu.postman_collection.json`
     - `parks-agent.postman_collection.json`

3. **Select the Environment**
   - In the upper-right corner, select environment:  
     🟢 **parks-prototype**



---

#### 🖼️ Example Outputs

| Input | Intent | Example Output |
|-------|--------|----------------|
| "Which U13 soccer fields..." | DATA_QUERY | Table of feasible fields with map links |
| "List turf areas overdue..." | DATA_QUERY | Grouped table of overdue mowing tasks |
| "If we upgrade Ball Field..." | DATA_QUERY | Table of permit hours affected |
| "Show parks with mismatched labor..." | DATA_QUERY | Dashboard summary with labor codes |
| Image upload + text | IMAGE_ASSESS | Condition score + labels ("disease", "bare_patch") |



