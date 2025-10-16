# 🌿 Parks Maintenance Intelligence System

A production-ready intelligent system for Vancouver parks maintenance operations, combining **RAG (Retrieval-Augmented Generation)**, **SQL analytics**, **LLM-enhanced insights**, and **interactive visualizations**.

---

## ✨ Key Features

- 🤖 **LLM-Enhanced RAG**: Uses Ollama (llama3.2:3b) to transform technical documents into clear, actionable insights
- 📊 **Interactive Visualizations**: Automatic chart generation (line charts, bar charts, timelines)
- 🎯 **Semantic Intent Classification**: SentenceTransformer-based few-shot learning for accurate query routing
- 🔍 **Multi-Modal Queries**: Supports text + SQL + document retrieval + image analysis
- ⚡ **High Performance**: DuckDB for fast SQL queries, FAISS for semantic search

---

## 🏗️ System Architecture

```
User Query
    ↓
┌─────────────────────┐
│  NLU (Semantic)     │  ← SentenceTransformer + Few-shot
│  - Intent Detection │
│  - Slot Extraction  │
│  - Template Routing │
└─────────────────────┘
    ↓
┌─────────────────────┐
│  Executor           │
│  - Tool Registry    │
│  - Plan Execution   │
└─────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Tools (Parallel/Sequential)            │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐│
│  │   RAG    │  │   SQL    │  │  CV   ││
│  │  FAISS   │  │ DuckDB   │  │ Mock  ││
│  └──────────┘  └──────────┘  └───────┘│
└─────────────────────────────────────────┘
    ↓
┌─────────────────────┐
│  Composer           │  ← LLM (Ollama) for summarization
│  - LLM Enhancement  │
│  - Chart Config     │
│  - Markdown Format  │
└─────────────────────┘
    ↓
Frontend (React + Recharts)
```

---

## 🧩 Project Structure

```
capstone_mvp/
│
├── Backend (FastAPI)
│   ├── app.py               # FastAPI server (/health, /nlu/parse, /agent/answer)
│   ├── nlu.py               # Semantic intent classification + slot extraction
│   ├── executor.py          # Tool orchestration and execution
│   ├── composer.py          # LLM-enhanced answer generation + chart config
│   │
│   ├── Tools/
│   │   ├── rag.py           # FAISS/BM25 retrieval + SOP extraction
│   │   ├── sql_tool.py      # DuckDB SQL templates (5 templates)
│   │   └── cv_tool.py       # Computer vision (mock + RAG)
│   │
│   ├── config.py            # Configuration and paths
│   │
│   └── data/
│       ├── 6 Mowing Reports to Jun 20 2025.xlsx
│       ├── rag_docs/
│       │   └── mowing_standard.pdf
│       └── faiss_index/     # Auto-generated FAISS index
│
└── Frontend (React + Vite)
    └── parks-ui/
        ├── src/
        │   ├── App.jsx      # Main UI with chart rendering
        │   ├── App.css      # Modern styling
        │   └── main.jsx
        ├── package.json
        └── vite.config.js
```

---

## 📊 Supported Query Types

### 1. **Cost Analysis** (RAG + SQL)
**Example**: *"Which park had the highest mowing cost in March 2025?"*

**System Response**:
- 🏆 SQL query result with park name and cost
- 📚 LLM-summarized context from mowing standards
- 📊 Bar chart visualization
- 📄 Data table
- 🔗 Citations to source documents

**SQL Template**: `mowing.labor_cost_month_top1`

---

### 2. **Trend Analysis** (SQL + Charts)
**Example**: *"Show mowing cost trend from January to June 2025"*

**System Response**:
- 📈 Multi-line chart (top 10 parks by cost)
- 📊 Monthly cost breakdown
- 📉 Trend data table

**SQL Template**: `mowing.cost_trend`

---

### 3. **Park Comparison** (SQL + Charts)
**Example**: *"Compare mowing costs across all parks in March 2025"*

**System Response**:
- 📊 Bar chart ranking all parks
- 💰 Total and average costs
- 📋 Detailed comparison table

**SQL Template**: `mowing.cost_by_park_month`

---

### 4. **Last Activity Tracking** (SQL + Timeline)
**Example**: *"When was the last mowing at Cambridge Park?"*

**System Response**:
- 📅 Timeline visualization
- 🕒 Last mowing date
- 📊 Session count and total cost

**SQL Template**: `mowing.last_mowing_date`

---

### 5. **SOP Queries** (Pure RAG)
**Example**: *"What are the mowing steps and safety requirements?"*

**System Response**:
- 📋 Structured steps, materials, tools, safety items
- 📚 Extracted from PDF standards
- 🔗 Source citations

**Tools**: `kb_retrieve` + `sop_extract`

---

### 6. **Detailed Breakdown** (SQL)
**Example**: *"Show cost breakdown by activity type for Garden Park"*

**SQL Template**: `mowing.cost_breakdown`

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Ollama (for LLM enhancement)

### 1️⃣ Install Ollama (LLM)

```bash
# macOS
brew install ollama

# Start Ollama
open -a Ollama

# Download model
ollama pull llama3.2:3b
```

### 2️⃣ Setup Backend

```bash
# Create environment
conda create -n capstone python=3.11
conda activate capstone

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

**Backend runs at**: http://127.0.0.1:8000

### 3️⃣ Setup Frontend

```bash
# Navigate to frontend
cd parks-ui

# Install dependencies
npm install

# Start dev server
npm run dev
```

**Frontend runs at**: http://localhost:5173

---

## 🔌 API Endpoints

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| GET | `/health` | System status and RAG mode | - |
| POST | `/nlu/parse` | Intent classification and slot extraction | `{"text": "...", "image_uri": "..."}` |
| POST | `/agent/answer` | Complete RAG+SQL+LLM pipeline | `{"text": "...", "image_uri": "..."}` |

### Example Response (`/agent/answer`)

```json
{
  "answer_md": "### 🏆 Results\n\n**Cambridge Park** had the highest mowing cost...",
  "tables": [{
    "name": "Top Park by Mowing Cost (3/2025)",
    "columns": ["park", "total_cost"],
    "rows": [{"park": "Cambridge Park", "total_cost": 1523.45}]
  }],
  "charts": [{
    "type": "bar",
    "title": "Mowing Cost by Park",
    "series": [...]
  }],
  "citations": [{
    "title": "Reference Document",
    "source": "mowing_standard.pdf#p12"
  }],
  "logs": [...]
}
```

---

## 🧠 NLU Intent Classification

Uses **SentenceTransformer** (all-MiniLM-L6-v2) with few-shot prototypes:

| Intent | Triggers | Tools |
|--------|----------|-------|
| `RAG+SQL_tool` | "highest cost", "top park" + cost query | kb_retrieve → sql_query_rag → LLM summary |
| `SQL_tool` | "trend", "compare", "breakdown" | sql_query_rag → chart generation |
| `RAG` | "steps", "procedure", "safety", "how to" | kb_retrieve → sop_extract |
| `CV_tool` | image upload | cv_assess_rag |
| `RAG+CV_tool` | image + text query | kb_retrieve → cv_assess_rag |

---

## 📈 SQL Templates

| Template Name | Purpose | Parameters | Returns |
|---------------|---------|------------|---------|
| `mowing.labor_cost_month_top1` | Find park with highest cost | month, year | 1 row (top park) |
| `mowing.cost_trend` | Monthly cost trend | start_month, end_month, year, park_name? | Time series data |
| `mowing.cost_by_park_month` | Compare all parks | month, year | All parks ranked |
| `mowing.last_mowing_date` | Last activity date | park_name? | Last mowing date(s) |
| `mowing.cost_breakdown` | Detailed by activity type | park_name?, month?, year | Activity breakdown |

---

## 🤖 LLM Integration (Ollama)

The system uses **Ollama** with **llama3.2:3b** to enhance RAG content:

### What it does:
- Transforms raw PDF text into coherent summaries
- Provides context for SQL results
- Explains standards and guidelines in plain language

### Configuration (composer.py):
```python
USE_LOCAL_LLM = True
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "llama3.2:3b"
```

### Fallback:
If Ollama is unavailable, automatically falls back to simple text formatting.

---

## 📊 Chart Types

The system automatically generates appropriate visualizations:

| Chart Type | Used For | Libraries |
|------------|----------|-----------|
| 📈 Line Chart | Cost trends over time | Recharts |
| 📊 Bar Chart | Park cost comparison | Recharts |
| 📊 Stacked Bar | Activity type breakdown | Recharts |
| 📅 Timeline | Last mowing dates | Custom React component |

---

## 🧪 Testing

### Health Check
```bash
curl http://127.0.0.1:8000/health
```

### NLU Parse
```bash
curl -X POST http://127.0.0.1:8000/nlu/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "Which park had the highest mowing cost in March 2025?"}'
```

### Full Agent Answer
```bash
curl -X POST http://127.0.0.1:8000/agent/answer \
  -H "Content-Type: application/json" \
  -d '{"text": "Show mowing cost trend from January to June 2025"}'
```

---

## 🎨 UI Features

### Modern Design
- Gradient backgrounds and shadows
- Smooth animations and transitions
- Responsive layout (desktop/tablet/mobile)

### Interactive Elements
- 5 preset query buttons
- Real-time chart rendering
- Collapsible sections
- Execution logs viewer

### Chart Capabilities
- Interactive tooltips
- Legend filtering
- Responsive sizing
- Export-ready visualizations

---

## 📦 Dependencies

### Backend
```
fastapi>=0.111         # Web framework
uvicorn[standard]>=0.30  # ASGI server
pydantic>=2.7          # Data validation
duckdb>=0.10.0         # SQL analytics
pandas==2.2.0          # Data processing
langchain              # RAG framework
faiss-cpu>=1.7.4       # Vector search
sentence-transformers  # Embeddings
openai>=1.12.0         # LLM API (Ollama)
```

### Frontend
```
react ^19.1.1
recharts ^2.13.3       # Chart library
vite ^7.1.7            # Build tool
```

---

## 🔧 Configuration

### Environment Variables (Optional)
```bash
# For OpenAI API (if not using Ollama)
export OPENAI_API_KEY="your-key-here"
```

### Data Paths (config.py)
```python
DATA_DIR = "data"
RAG_DOC_DIR = "data/rag_docs"
FAISS_DIR = "data/faiss_index"
LABOR_XLSX = "data/6 Mowing Reports to Jun 20 2025.xlsx"
```

---

## 📸 Screenshots

### Query with Chart Visualization
```
User: "Show mowing cost trend from January to June 2025"

System Response:
├── 📈 Line chart (top 10 parks)
├── 📊 Trend Analysis summary
├── 📋 Data table (517 rows)
└── 🔗 Citations
```

### RAG + SQL Integration
```
User: "Which park had the highest mowing cost in March 2025?"

System Response:
├── 🏆 Cambridge Park - $1,523.45
├── 📚 LLM-summarized context from standards
├── 📊 Bar chart
└── 📄 Detailed cost table
```

---

## 🎯 Use Cases

### 1. **Budget Planning**
- Identify high-cost parks
- Analyze cost trends
- Compare parks across periods

### 2. **Operational Compliance**
- Access mowing SOPs
- Check safety requirements
- Review standard procedures

### 3. **Maintenance Scheduling**
- Track last mowing dates
- Identify overdue locations
- Monitor service frequency

### 4. **Performance Analysis**
- Compare contractor costs
- Analyze activity types
- Track seasonal patterns

---

## 🚧 Advanced Features

### LLM-Enhanced RAG
The system uses a lightweight LLM to:
- Summarize technical PDF content
- Provide context for SQL results
- Explain standards in plain language
- Generate actionable insights

**Example Enhancement**:
```
Raw PDF: "ITEM # CLASS OF WORK LOCATION UNIT PRICE COMPLETE..."

LLM Summary: "Based on the reference documents, mowing costs vary by 
park size and terrain complexity. Standard rates are $X per square 
meter, with 2-week frequency requirements during growing season."
```

### Automatic Chart Selection
The system intelligently selects chart types based on:
- Query intent
- Data structure
- Number of data points
- Template type

### Smart Template Routing
NLU uses pattern matching with priority levels:
1. Exact matches (highest, top, max)
2. Temporal queries (last, recent)
3. Trend queries (from X to Y)
4. Comparison queries (compare, across)
5. Fallback to default

---

## 🛠️ Development

### Adding New SQL Templates

1. **Define template function** in `sql_tool.py`:
```python
def _tpl_your_template(con, params):
    sql = "SELECT ..."
    rows = con.execute(sql).fetchdf().to_dict(orient="records")
    return {"rows": rows, "rowcount": len(rows), "elapsed_ms": ...}
```

2. **Register template**:
```python
TEMPLATE_REGISTRY = {
    "mowing.your_template": _tpl_your_template,
}
```

3. **Add NLU pattern** in `nlu.py`:
```python
if "your_keyword" in lowq:
    template_hint = "mowing.your_template"
```

4. **Add prototype examples**:
```python
INTENT_PROTOTYPES = {
    "SQL_tool": [
        "Your example question here",
    ]
}
```

---

## 🧪 Testing Examples

### Test Different Query Types

```python
# Cost ranking
"Which park had the highest mowing cost in March 2025?"

# Trend analysis  
"Show mowing cost trend from January to June 2025"

# Park comparison
"Compare mowing costs across all parks in March 2025"

# Last activity
"When was the last mowing at Cambridge Park?"

# SOP queries
"What are the mowing steps and safety requirements?"

# Detailed breakdown
"Show cost breakdown by activity type for all parks"
```

---

## 🎨 UI Customization

The frontend uses a modern design system with:
- CSS variables for easy theming
- Responsive grid layout
- Smooth animations
- Custom chart styling

Edit `App.css` to customize:
```css
:root {
  --bg: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --card: #ffffff;
  --blue: #3b82f6;
  /* ... */
}
```

---

## 🔒 Data Privacy

- All processing happens locally
- DuckDB runs in-process
- Ollama runs on localhost
- No external API calls (unless using OpenAI)

---

## 📈 Performance Metrics

| Component | Response Time |
|-----------|--------------|
| NLU Classification | ~50ms |
| SQL Query (DuckDB) | ~5-20ms |
| RAG Retrieval (FAISS) | ~10-30ms |
| LLM Summary (Ollama) | ~500ms-2s |
| Total E2E | ~1-3s |

*Tested on M1 MacBook Pro*

---

## 🐛 Troubleshooting

### Ollama not responding
```bash
# Check if running
curl http://localhost:11434/api/tags

# Restart Ollama
open -a Ollama
```

### FAISS index issues
```bash
# Delete and rebuild index
rm -rf data/faiss_index/*
# Restart backend (will auto-rebuild)
```

### NLU template mismatch
Check terminal logs for:
```
[NLU] Template hint: mowing.labor_cost_month_top1
```

---

## 🚀 Future Enhancements

- [ ] Real computer vision model integration
- [ ] Multi-document RAG (permits, horticulture)
- [ ] Advanced LLM features (query rewriting, multi-turn dialogue)
- [ ] Export reports (PDF, Excel)
- [ ] User authentication and session management
- [ ] Mobile app (React Native)
- [ ] Real-time data streaming
- [ ] Advanced analytics dashboard


---

## 📄 License

This project is part of a capstone project at Northeastern University.

---

## 🙏 Acknowledgments

- LangChain for RAG framework
- Ollama for local LLM inference
- Recharts for visualization
- FastAPI for backend framework
- Vancouver Parks Board for domain expertise
```