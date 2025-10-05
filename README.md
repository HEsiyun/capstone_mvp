# Parks Prototype (Baseline Multimodal RAG Agent)

This project is a prototype multimodal chatbot for parks asset management.  
It supports both text and image queries, performing:
- **NLU** (intent detection + slot extraction),
- **Tool calls** (SQL queries, CV analysis, SOP retrieval),
- **Answer composition** (tables, SOP instructions, assessments).
目前是没有接任何数据进来的，纯mock
---

## 1. Setup Environment

We recommend Python **3.11** and Node.js **18+**.

### Backend (FastAPI)
```bash
# Create a new Python environment (conda or venv)
conda create -n parks-proto python=3.11
conda activate parks-proto

# Install dependencies
pip install -r requirements.txt
```

### Run the FastAPI server:
```bash
uvicorn app:app --reload --port 8000
```
The backend will now be available at:
👉 http://127.0.0.1:8000

### Frontend (React + Vite)
```bash
# Move into frontend folder
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```


# 🧪 Parks Prototype – API Testing with Postman

This guide explains how to test your **FastAPI backend** endpoints using **Postman**.  
You’ll be able to run both `/nlu/parse` and `/agent/answer` requests interactively,  
see example outputs, and verify that your prototype pipeline works end-to-end.

---

## 📁 Files Overview

| File | Description |
|------|--------------|
| **`parks-prototype.postman_environment.json`** | Defines your base URL variable (`{{base_url}} = http://127.0.0.1:8000`) |
| **`parks-nlu.postman_collection.json`** | Tests the **NLU module** (`/nlu/parse`) for intent detection and slot extraction |
| **`parks-agent.postman_collection.json`** | Tests the **RAG-Agent pipeline** (`/agent/answer`) for tool execution and answer composition |

---

## 🧩 Prerequisites

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

## 🧰 Import Collections into Postman

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

## 🚀 Run the Tests

### 1️⃣ `/nlu/parse` – NLU Intent Detection

- Open the **Parks NLU** collection.  
- Choose **"Playgrounds need inspection"** and click **Send**.  
- You should see structured output like this:

```json
{
  "intent": "DATA_QUERY",
  "confidence": 0.82,
  "slots": {
    "asset_type": "playground",
    "location": {"park_name": "Stanley Park"},
    "inspection_threshold_days": 180
  },
  "route_plan": [
    {"tool": "sql_query", "args": {"template": "assets_overdue_by_type_and_park", "params": {...}}}
  ]
}
```

🧠 **This endpoint only runs the NLU module**, classifying the query and building a tool plan.  
No external tools are executed yet.

---

### 2️⃣ `/agent/answer` – Full RAG-Agent Flow

- Open **Parks Agent** collection.  
- Try **“Get Maintenance Steps (SOP)”** or **“Bench Image Assessment”**.  
- Click **Send** to run a complete pipeline.

Example output:

```json
{
  "answer_md": "**Maintenance SOP for playground**\n\n### Steps\n1. Inspect slide surface...",
  "tables": [],
  "citations": [{"title": "Manual snippet", "source": "kb_manuals/playground_sop.pdf#p4"}],
  "logs": [
    {"tool": "kb_retrieve", "elapsed_ms": 25, "ok": true},
    {"tool": "sop_extract", "elapsed_ms": 17, "ok": true}
  ]
}
```

🧩 **This endpoint runs NLU + all tools (SQL, CV, KB)** and returns a fully composed Markdown answer.

---

## ⚠️ Common Issues

| Problem | Likely Cause | Fix |
|----------|---------------|-----|
| `405 Method Not Allowed` | Missing CORS headers | Confirm your `app.py` includes CORSMiddleware |
| No response / timeout | Backend not running | Run `uvicorn app:app --reload --port 8000` |
| `base_url` undefined | Forgot to select environment | Select **parks-prototype** in Postman |

---

## ✅ Quick Recap

| Step | Action | Result |
|------|---------|--------|
| 1 | Run backend server | API available at `localhost:8000` |
| 2 | Import Postman files | Pre-built requests ready |
| 3 | Test `/nlu/parse` | See classified intents & slots |
| 4 | Test `/agent/answer` | See full multimodal RAG output |
