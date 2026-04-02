import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Gemini settings
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_EMBEDDING_MODEL = "models/gemini-embedding-001"

# Chunking settings
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Project paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_llm():
    """Return the Gemini LLM."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.3,
    )


def get_embeddings():
    """Return the Gemini embeddings model."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )
