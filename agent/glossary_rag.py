"""
agent/glossary_rag.py — RAG over business glossary docs.

Interview talking point:
"I embed business term definitions into Chroma and inject the top-K
 most relevant chunks into the SQL prompt. This makes the agent
 domain-aware without hard-coding business logic into prompts."
"""
import os
from pathlib import Path
from typing import Optional
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from .config import (
    EMBEDDING_MODEL,
    VECTORSTORE_DIR,
    GLOSSARY_DIR,
    TOP_K,
)

_vectorstore: Optional[Chroma] = None


def _load_glossary_docs() -> list[Document]:
    """Load all .md files from the glossary directory."""
    docs = []
    glossary_path = Path(GLOSSARY_DIR)
    if not glossary_path.exists():
        return docs

    for md_file in glossary_path.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        docs.append(
            Document(
                page_content=text,
                metadata={"source": md_file.name},
            )
        )
    return docs


def _build_vectorstore() -> Chroma:
    """Build or load the persistent Chroma vectorstore."""
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # If the vectorstore already exists on disk, load it
    if Path(VECTORSTORE_DIR).exists() and any(Path(VECTORSTORE_DIR).iterdir()):
        return Chroma(
            persist_directory=VECTORSTORE_DIR,
            embedding_function=embeddings,
            collection_name="glossary",
        )

    # Otherwise build from scratch
    raw_docs = _load_glossary_docs()
    if not raw_docs:
        # Return an empty store so the app doesn't crash
        return Chroma(
            persist_directory=VECTORSTORE_DIR,
            embedding_function=embeddings,
            collection_name="glossary",
        )

    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=60)
    splits = splitter.split_documents(raw_docs)

    store = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=VECTORSTORE_DIR,
        collection_name="glossary",
    )
    return store


def get_vectorstore() -> Chroma:
    """Singleton accessor — build once, reuse."""
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _build_vectorstore()
    return _vectorstore


def retrieve(question: str) -> str:
    """
    Retrieve the top-K glossary chunks most relevant to the question.
    Returns a formatted string ready to inject into the SQL prompt.
    """
    store = get_vectorstore()
    try:
        results = store.similarity_search(question, k=TOP_K)
    except Exception:
        return ""

    if not results:
        return ""

    chunks = [f"[{doc.metadata.get('source', 'glossary')}]\n{doc.page_content}" for doc in results]
    return "\n\n---\n\n".join(chunks)


def rebuild_index() -> int:
    """
    Force-rebuild the Chroma index from glossary docs.
    Returns number of chunks indexed.
    Useful as a management command.
    """
    global _vectorstore
    import shutil
    if Path(VECTORSTORE_DIR).exists():
        shutil.rmtree(VECTORSTORE_DIR)
    _vectorstore = None
    store = _build_vectorstore()
    _vectorstore = store
    try:
        return store._collection.count()
    except Exception:
        return -1
