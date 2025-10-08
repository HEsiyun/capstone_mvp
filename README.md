# 🌿 Parks RAG-Agent Prototype (Baseline v0.3)

This prototype demonstrates a multimodal RAG-based assistant for Vancouver Park Operations.
It supports turf, sport field, and horticulture queries across multiple data sources — including GIS, inspection, consultant, and labor data.

---

## 🧩 System Overview

### Architecture

The system converts natural language (text or image queries) into structured evidence-based answers.

#### 1. NLU (Intent + Slot Extraction)

* Classifies intent (Data Query / SOP Query / Image Assess).
* Extracts fields such as `asset_type`, `park_name`, and `analysis_type`.
* Implemented via rule-based heuristics, upgradable to a small LM classifier.

#### 2. MRAG-Agent (Multimodal RAG Orchestrator)

* Decides which tool(s) to call based on intent.
* Supported mock tools:
  * `sql_query`: template-based SQL queries over GIS / permit / labor data
  * `cv_assess`: zero-shot CV model for condition scoring
  * `kb_retrieve` + `sop_extract`: simple RAG retrieval + pattern-based SOP extraction

#### 3. Evidence Fusion & Answer Composer

* Combines tool outputs into final structured answers.
* Returns markdown text, tables, and optional map layers.
* Includes uncertainty flags and citations.

---

## 🧠 Supported Query Types

| Intent | Example Query | Mock Tool Path |
|--------|---------------|----------------|
| **Field Feasibility** | "Which U13 soccer fields can be adjusted to meet size standards?" | SQL (GIS / consultant) |
| **Maintenance SLA** | "List turf areas overdue for mowing by more than 7 days, grouped by district." | SQL (turf inspection) |
| **Permit Impact** | "If we upgrade Ball Field SF-101, how many permit hours would be affected?" | SQL (permit history) |
| **Labor Dashboard** | "Show parks with mismatched mowing labor codes in September." | SQL (SAP labor data) |
| **Image Assess** (optional) | "Check this photo — does the turf show signs of disease or wear?" | CV model |

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


### 4️⃣ Testing with Postman

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