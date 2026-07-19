"""
agent/config.py — Central configuration for the AI agent.
Change these values to adjust model, retrieval, and safety settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ─── LLM ─────────────────────────────────────────────────────────────────────
MODEL_NAME: str = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# ─── RAG ─────────────────────────────────────────────────────────────────────
TOP_K: int = 3                          # number of glossary chunks to retrieve
VECTORSTORE_DIR: str = str(BASE_DIR / "vectorstore")
GLOSSARY_DIR: str = str(BASE_DIR / "glossary" / "docs")

# ─── Agent ───────────────────────────────────────────────────────────────────
MAX_RETRIES: int = 2                    # verifier loop retries before giving up
QUERY_TIMEOUT_SECS: int = 30            # max seconds for a single SQL query
MAX_ROWS_LIMIT: int = 1000              # injected LIMIT if agent omits one

# ─── Target Database (read-only) ─────────────────────────────────────────────
TARGET_DB_URL: str = (
    f"mysql+pymysql://"
    f"{os.getenv('TARGET_DB_USER', 'root')}:"
    f"{os.getenv('TARGET_DB_PASSWORD', '')}@"
    f"{os.getenv('TARGET_DB_HOST', 'localhost')}:"
    f"{os.getenv('TARGET_DB_PORT', '3306')}/"
    f"{os.getenv('TARGET_DB_NAME', 'sales_db')}"
)

# ─── Media ───────────────────────────────────────────────────────────────────
CHARTS_DIR: str = str(BASE_DIR / "media" / "charts")


# ─── LLM Instantiation Helper ────────────────────────────────────────────────
def get_llm(temperature: float = 1.0):
    """
    Returns the configured LLM. Reads OPENAI_API_KEY from .env.
    Falls back to ChatGoogleGenerativeAI if GOOGLE_API_KEY is set instead.
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")

    if openai_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            api_key=openai_key,
            temperature=temperature,
        )

    if google_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("MODEL_NAME", "gemini-2.0-flash"),
            temperature=temperature,
            google_api_key=google_key,
        )

    raise EnvironmentError(
        "No LLM API key found. Set OPENAI_API_KEY or GOOGLE_API_KEY in your .env file."
    )
