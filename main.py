import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config import UPLOAD_DIR
import rag_engine


# ── Lifespan ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Starting RAG Chatbot")
    rag_engine.load_default_pdf()
    yield
    print("👋 Shutting down RAG Chatbot")


# ── App ─────────────────────────────────────────────────────────
app = FastAPI(title="RAG Chatbot", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Models ──────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    collection: str | None = None


class ChatResponse(BaseModel):
    answer: str
    collection: str | None = None


# ── Routes ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    try:
        answer = rag_engine.query(body.question, body.collection)
        active = body.collection or rag_engine.get_active_collection()
        return ChatResponse(answer=answer, collection=active)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # Validate extension
    allowed = {".pdf", ".docx", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed)}",
        )

    # Save file
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Process
    try:
        col_name = rag_engine.process_document(save_path, file.filename)
        docs = rag_engine.get_documents()
        doc_info = next((d for d in docs if d["collection_name"] == col_name), {})
        return {
            "status": "success",
            "message": f"'{file.filename}' processed successfully",
            "document": doc_info,
        }
    except Exception as e:
        # Clean up on failure
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def documents():
    return {"documents": rag_engine.get_documents()}


# ── Entry Point ─────────────────────────────────────────────────
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)