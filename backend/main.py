import os
import shutil
import logging
from typing import List

from dotenv import load_dotenv
load_dotenv()  # reads GROQ_API_KEY (and GROQ_MODEL) from a .env file in this folder

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LangChain Groq RAG Service")

# The React app calls this API directly from the browser, so CORS must allow
# its origin explicitly. Set FRONTEND_URL in .env — e.g. your Vercel domain
# in production, http://localhost:5173 for local Vite dev.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
# NEVER hardcode API keys in source. Read from the environment only, and
# fail loudly at startup if it's missing so you don't debug a 500 later.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Create a .env file (see .env.example) "
        "or export it in your shell before starting the server."
    )

# llama-3.3-70b-versatile was deprecated by Groq (announced 2026-06-17) and
# no longer resolves — that's the 404 model_not_found error you hit.
# openai/gpt-oss-120b is Groq's recommended replacement for it.
# Override via env var if you want to swap models without editing code.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

DB_DIR = "./vector_db"
TEMP_DIR = "./temp_docs"

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
llm = ChatGroq(model=GROQ_MODEL, temperature=0.1, api_key=GROQ_API_KEY)


class QueryRequest(BaseModel):
    question: str


@app.get("/health")
async def health_check():
    return {"status": "online", "service": "LangChain Groq RAG Service", "model": GROQ_MODEL}


@app.get("/models")
async def list_models():
    """
    Quick way to confirm which model IDs your Groq key can actually use,
    without leaving this service. Handy if a model gets deprecated again.
    """
    import requests

    try:
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"models": [m["id"] for m in data.get("data", [])]}
    except Exception as e:
        logger.error(f"Error fetching model list: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Could not reach Groq: {e}")


@app.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    os.makedirs(TEMP_DIR, exist_ok=True)
    docs = []

    try:
        for file in files:
            if not file.filename.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail=f"'{file.filename}' is not a PDF. Only PDF uploads are supported.",
                )
            file_path = os.path.join(TEMP_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            loader = PyPDFLoader(file_path)
            docs.extend(loader.load())

        if not docs:
            raise HTTPException(status_code=400, detail="No readable text found in the uploaded PDF(s).")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)

        # langchain_chroma persists automatically — no manual .persist() call needed
        # (and calling it on this class would raise AttributeError).
        Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=DB_DIR,
        )

        return {"message": f"Successfully ingested {len(files)} file(s) into {len(splits)} chunks."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    finally:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)


@app.post("/chat")
async def chat_with_docs(request: QueryRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        if not os.path.exists(DB_DIR):
            raise HTTPException(status_code=400, detail="No documents found. Please upload first.")

        vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
        if vectorstore._collection.count() == 0:
            raise HTTPException(status_code=400, detail="Vector store is empty. Please upload documents.")

        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

        system_prompt = (
            "You are an assistant for question-answering tasks. "
            "Use the following pieces of retrieved context to answer "
            "the question. If you don't know, say that you don't know.\n\n"
            "{context}"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        rag_chain = (
            {
                "context": retriever | format_docs,
                "input": RunnablePassthrough(),
            }
            | prompt
            | llm
            | StrOutputParser()
        )

        answer = rag_chain.invoke(request.question)
        return {"answer": answer}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /chat: {e}", exc_info=True)
        # Bubble up the real Groq/langchain error so it's visible in Laravel's
        # response too (this is exactly how the model_not_found error surfaced).
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
