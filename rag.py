from __future__ import annotations
import os, glob, re
from typing import Any, Dict, List, Optional
from config import RAG_DOC_DIR, FAISS_DIR, NUMPY_AVAILABLE

# LangChain bits
from langchain_community.retrievers import BM25Retriever
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class RAGIndex:
    """
    Primary: FAISS + HF embeddings (if numpy exists)
    Fallback: BM25 (no embeddings needed)
    Supports: PDF and TXT files
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
        """Load both PDF and TXT files from doc directory"""
        docs = []
        
        # Load PDFs
        pdfs = sorted(glob.glob(os.path.join(self.doc_dir, "*.pdf")))
        for p in pdfs:
            try:
                loaded = PyPDFLoader(p).load()
                docs.extend(loaded)
                print(f"[RAG] Loaded PDF: {os.path.basename(p)} ({len(loaded)} pages)")
            except Exception as e:
                print(f"[RAG] Failed to load PDF {p}: {e}")
        
        # Load TXT files
        txts = sorted(glob.glob(os.path.join(self.doc_dir, "*.txt")))
        for t in txts:
            try:
                loaded = TextLoader(t, encoding='utf-8').load()
                docs.extend(loaded)
                print(f"[RAG] Loaded TXT: {os.path.basename(t)} ({len(loaded)} docs)")
            except Exception as e:
                print(f"[RAG] Failed to load TXT {t}: {e}")
        
        print(f"[RAG] Total documents loaded: {len(docs)}")
        return docs

    def _ensure_index(self):
        docs = self._load_docs()
        if not docs:
            self.mode = "none"
            print("[RAG] No documents found in", self.doc_dir)
            return

        if NUMPY_AVAILABLE:
            try:
                self.emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                if os.path.isdir(self.faiss_dir) and os.listdir(self.faiss_dir):
                    self.vs = FAISS.load_local(self.faiss_dir, self.emb, allow_dangerous_deserialization=True)
                    self.mode = "faiss"
                    print(f"[RAG] Loaded existing FAISS index")
                    return
                
                splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
                chunks = splitter.split_documents(docs)
                print(f"[RAG] Created {len(chunks)} chunks from {len(docs)} documents")
                
                self.vs = FAISS.from_documents(chunks, self.emb)
                self.vs.save_local(self.faiss_dir)
                self.mode = "faiss"
                print(f"[RAG] Built and saved new FAISS index")
                return
            except Exception as e:
                print(f"[RAG] FAISS failed → BM25 fallback: {e}")

        try:
            splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
            chunks = splitter.split_documents(docs)
            self.retriever = BM25Retriever.from_documents(chunks)
            self.retriever.k = 5
            self.mode = "bm25"
            print(f"[RAG] Using BM25 retriever with {len(chunks)} chunks")
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
    """Retrieve knowledge base document snippets"""
    return {"hits": RAG.retrieve(query, k=top_k) if query else []}

def sop_extract(snippets: List[str], schema: Optional[List[str]] = None):
    """
    Extract structured SOP information from document snippets
    
    Args:
        snippets: List of document text snippets
        schema: Optional extraction schema (reserved for future use)
    """
    # Handle empty input
    if not snippets:
        return {"steps": [], "materials": [], "tools": [], "safety": []}
    
    text = "\n".join(snippets)
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    def pick(pred): 
        return [l for l in lines if pred(l)]
    
    # Extract steps (lines with numbers or bullets)
    steps = [l for l in lines if re.match(r"^(\d+[\).\s]|•|-)\s", l)]
    
    # Extract materials
    mats = pick(lambda l: re.search(
        r"(material|fertilizer|seed|mulch|line|marking|fuel)", l, re.I
    ))
    
    # Extract tools
    tools = pick(lambda l: re.search(
        r"(mower|edger|trimmer|blower|truck|line marker|roller|equipment)", l, re.I
    ))
    
    # Extract safety items
    safety = pick(lambda l: re.search(
        r"(safety|PPE|goggles|hearing|lockout|traffic|cone)", l, re.I
    ))
    
    # Deduplicate
    dedup = lambda xs: list(dict.fromkeys(xs))
    
    return {
        "steps": dedup(steps)[:12], 
        "materials": dedup(mats)[:10],
        "tools": dedup(tools)[:10], 
        "safety": dedup(safety)[:10]
    }