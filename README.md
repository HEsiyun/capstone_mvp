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