import os
import glob
import hashlib
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

from config import get_llm, get_embeddings, CHUNK_SIZE, CHUNK_OVERLAP, BASE_DIR


# ── In-memory store of collections! ──────────────────────────────
_collections: dict[str, Chroma] = {}
_doc_metadata: dict[str, dict] = {}  # collection_name -> {filename, chunk_count}

# ── Text Splitter ───────────────────────────────────────────────
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
)

# ── QA Prompt ───────────────────────────────────────────────────
QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant that answers questions based on the provided context.
Use ONLY the context below to answer the question. If the answer is not in the context, say
"I don't have enough information in the provided documents to answer that question."

Context:
{context}"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}")
])

# Global store for chat histories
_store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in _store:
        _store[session_id] = ChatMessageHistory()
    return _store[session_id]


def _collection_name(filename: str) -> str:
    """Generate a safe, unique collection name from a filename."""
    safe = hashlib.md5(filename.encode()).hexdigest()[:10]
    base = "".join(c if c.isalnum() else "_" for c in filename)[:30]
    return f"{base}_{safe}"


def _load_file(file_path: str) -> list[Document]:
    """Load documents from a file path based on extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path).load()
    elif ext == ".docx":
        return Docx2txtLoader(file_path).load()
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return [Document(page_content=text, metadata={"source": file_path})]
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _format_docs(docs: list[Document]) -> str:
    """Format retrieved documents into a single string."""
    return "\n\n".join(doc.page_content for doc in docs)


def process_document(file_path: str, original_filename: Optional[str] = None) -> str:
    """
    Process a document: load, split, embed, and store in ChromaDB.
    Returns the collection name.
    """
    filename = original_filename or os.path.basename(file_path)
    col_name = _collection_name(filename)

    # Skip if already loaded
    if col_name in _collections:
        return col_name

    # Load and split
    docs = _load_file(file_path)
    chunks = _splitter.split_documents(docs)

    if not chunks:
        raise ValueError(f"No content extracted from {filename}")

    # Create vector store
    embeddings = get_embeddings()
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=col_name,
    )

    _collections[col_name] = vectorstore
    _doc_metadata[col_name] = {
        "filename": filename,
        "chunk_count": len(chunks),
        "page_count": len(docs),
    }

    return col_name


def query(question: str, collection_name: Optional[str] = None) -> str:
    """
    Query the RAG pipeline using LCEL.
    If no collection specified, uses the first available.
    """
    if not _collections:
        return "No documents have been loaded yet. Please upload a document first."

    if collection_name and collection_name in _collections:
        vectorstore = _collections[collection_name]
    else:
        # Use the first loaded collection
        vectorstore = next(iter(_collections.values()))

    llm = get_llm()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # LCEL chain
    chain = (
        RunnablePassthrough.assign(context=(lambda x: x["question"]) | retriever | _format_docs)
        | QA_PROMPT
        | llm
        | StrOutputParser()
    )

    with_message_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )

    result = with_message_history.invoke(
        {"question": question},
        config={"configurable": {"session_id": "default"}}
    )
    return result


def load_default_pdf() -> Optional[str]:
    """
    Auto-index the first PDF found at the project root.
    Returns collection name or None if no PDF found.
    """
    pdf_files = glob.glob(os.path.join(BASE_DIR, "*.pdf"))
    if pdf_files:
        pdf_path = pdf_files[0]
        filename = os.path.basename(pdf_path)
        print(f"📄 Auto-loading default PDF: {filename}")
        col_name = process_document(pdf_path, filename)
        print(f"✅ Indexed '{filename}' ({_doc_metadata[col_name]['chunk_count']} chunks)")
        return col_name
    else:
        print("⚠️  No PDF found at project root. Starting with empty vector store.")
        return None


def get_documents() -> list[dict]:
    """Return metadata for all loaded document collections."""
    return [
        {
            "collection_name": col_name,
            "filename": meta["filename"],
            "chunk_count": meta["chunk_count"],
            "page_count": meta["page_count"],
        }
        for col_name, meta in _doc_metadata.items()
    ]


def get_active_collection() -> Optional[str]:
    """Return the first available collection name, or None."""
    if _collections:
        return next(iter(_collections.keys()))
    return None
