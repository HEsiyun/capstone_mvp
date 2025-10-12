# FastAPI wiring
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from nlu import nlu_parse
from executor import execute_plan
from composer import compose_answer
from rag import RAG  # to expose health info (mode)

class NLUReq(BaseModel):
    text: str
    image_uri: Optional[str] = None

class AgentReq(BaseModel):
    text: str
    image_uri: Optional[str] = None
    nlu: Optional[Dict[str, Any]] = None

app = FastAPI(title="Parks Prototype API (RAG)", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat(), "rag_mode": getattr(RAG, "mode", "none")}

@app.post("/nlu/parse")
def nlu_endpoint(req: NLUReq):
    return nlu_parse(req.text, req.image_uri)

@app.post("/agent/answer")
def agent_answer(req: AgentReq):
    nlu = req.nlu or nlu_parse(req.text, req.image_uri)
    state = execute_plan(nlu["route_plan"], nlu["slots"])
    return compose_answer(nlu, state)