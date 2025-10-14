from __future__ import annotations
import os, glob, re
from typing import Any, Dict, List, Optional
from config import RAG_DOC_DIR, FAISS_DIR, NUMPY_AVAILABLE

# LangChain bits
from langchain_community.retrievers import BM25Retriever
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class RAGIndex:
    """
    Primary: FAISS + HF embeddings (if numpy exists)
    Fallback: BM25 (no embeddings needed)
    """
    def __init__(self, doc_dir: str, faiss_dir: str):
        self.doc_dir = doc_dir
        self.faiss_dir = faiss_dir
        self.mode: str = "none"   # "faiss" | "bm25" | "none"
        self.emb = None
        self.vs: Optional[FAISS] = None
        self.retriever = None
        self._ensure_index()

    def _load_docs(self):
        pdfs = sorted(glob.glob(os.path.join(self.doc_dir, "*.pdf")))
        docs = []
        for p in pdfs:
            try:
                docs.extend(PyPDFLoader(p).load())
            except Exception:
                pass
        return docs

    def _ensure_index(self):
        docs = self._load_docs()
        if not docs:
            self.mode = "none"
            return

        if NUMPY_AVAILABLE:
            try:
                self.emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                if os.path.isdir(self.faiss_dir) and os.listdir(self.faiss_dir):
                    self.vs = FAISS.load_local(self.faiss_dir, self.emb, allow_dangerous_deserialization=True)
                    self.mode = "faiss"
                    return
                splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
                chunks = splitter.split_documents(docs)
                self.vs = FAISS.from_documents(chunks, self.emb)
                self.vs.save_local(self.faiss_dir)
                self.mode = "faiss"
                return
            except Exception as e:
                print(f"[RAG] FAISS failed → BM25 fallback: {e}")

        try:
            splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
            chunks = splitter.split_documents(docs)
            self.retriever = BM25Retriever.from_documents(chunks)
            self.retriever.k = 5
            self.mode = "bm25"
        except Exception as e:
            print(f"[RAG] BM25 failed: {e}")
            self.mode = "none"

    def retrieve(self, query: str, k: int = 4):
        hits = []
        if self.mode == "faiss" and self.vs is not None:
            docs = self.vs.similarity_search_with_score(query, k=k)
            for i, (d, score) in enumerate(docs):
                meta = d.metadata or {}
                hits.append({
                    "doc_id": os.path.basename(meta.get("source", "unknown")),
                    "chunk_id": f"{i}",
                    "text": d.page_content,
                    "page": int(meta.get("page", 0)) + 1 if "page" in meta else None,
                    "image_ref": None,
                    "score": float(score),
                    "source": f"{meta.get('source','')}#p{int(meta.get('page',0))+1 if 'page' in meta else ''}",
                })
            return hits

        if self.mode == "bm25" and self.retriever is not None:
            docs = self.retriever.get_relevant_documents(query)
            for i, d in enumerate(docs[:k]):
                meta = d.metadata or {}
                hits.append({
                    "doc_id": os.path.basename(meta.get("source", "unknown")),
                    "chunk_id": f"{i}",
                    "text": d.page_content,
                    "page": int(meta.get("page", 0)) + 1 if "page" in meta else None,
                    "image_ref": None,
                    "score": float(1.0 / (i + 1)),
                    "source": f"{meta.get('source','')}#p{int(meta.get('page',0))+1 if 'page' in meta else ''}",
                })
            return hits
        return []

# Global index instance
RAG = RAGIndex(RAG_DOC_DIR, FAISS_DIR)

def kb_retrieve(query: str, top_k: int = 3, filters: Optional[dict] = None):
    """检索知识库文档片段"""
    return {"hits": RAG.retrieve(query, k=top_k) if query else []}

def sop_extract(snippets: List[str], schema: Optional[List[str]] = None):
    """
    从文档片段中提取结构化SOP信息
    
    Args:
        snippets: 文档文本片段列表
        schema: 可选的提取模式（当前版本未使用，保留用于未来扩展）
    """
    # 处理空输入
    if not snippets:
        return {"steps": [], "materials": [], "tools": [], "safety": []}
    
    text = "\n".join(snippets)
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    def pick(pred): 
        return [l for l in lines if pred(l)]
    
    # 提取步骤（带编号或符号的行）
    steps = [l for l in lines if re.match(r"^(\d+[\).\s]|•|-)\s", l)]
    
    # 提取材料
    mats = pick(lambda l: re.search(
        r"(material|fertilizer|seed|mulch|line|marking|fuel)", l, re.I
    ))
    
    # 提取工具
    tools = pick(lambda l: re.search(
        r"(mower|edger|trimmer|blower|truck|line marker|roller|equipment)", l, re.I
    ))
    
    # 提取安全事项
    safety = pick(lambda l: re.search(
        r"(safety|PPE|goggles|hearing|lockout|traffic|cone)", l, re.I
    ))
    
    # 去重
    dedup = lambda xs: list(dict.fromkeys(xs))
    
    return {
        "steps": dedup(steps)[:12], 
        "materials": dedup(mats)[:10],
        "tools": dedup(tools)[:10], 
        "safety": dedup(safety)[:10]
    }