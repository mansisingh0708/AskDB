"""
agent/query_cache.py — Semantic SQL plan caching layer.
"""
from typing import Optional, Dict, Any
import json
import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from sqlalchemy import create_engine, text as sa_text

from .config import EMBEDDING_MODEL, VECTORSTORE_DIR, TARGET_DB_URL

_cache_store: Optional[Chroma] = None


def get_cache_store() -> Chroma:
    """Lazy initializer for the Chroma SQL cache collection."""
    global _cache_store
    if _cache_store is None:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        
        import shutil
        flag_file = os.path.join(VECTORSTORE_DIR, "rebuilt_v5.flag")
        if os.path.exists(VECTORSTORE_DIR) and not os.path.exists(flag_file):
            try:
                shutil.rmtree(VECTORSTORE_DIR)
                print("[SQL Cache] Cleared legacy cache directory for v5 plan caching support.")
            except Exception as e:
                print(f"[SQL Cache] Failed to clear legacy cache directory: {e}")

        os.makedirs(VECTORSTORE_DIR, exist_ok=True)
        try:
            with open(flag_file, "w") as f:
                f.write("rebuilt_v5")
        except Exception as e:
            print(f"[SQL Cache] Failed to write flag file: {e}")

        _cache_store = Chroma(
            persist_directory=VECTORSTORE_DIR,
            embedding_function=embeddings,
            collection_name="sql_plan_cache",
        )
    return _cache_store


def check_cache(question: str) -> Optional[Dict[str, Any]]:
    """
    Check the semantic cache for a question.
    Returns cached plan details if similarity is extremely high (>95%), else None.
    """
    try:
        store = get_cache_store()
        results = store.similarity_search_with_score(question, k=1)
        if not results:
            return None

        doc, distance = results[0]
        print(f"[SQL Cache] Query: '{question}' -> Match: '{doc.page_content}' (distance: {distance:.4f})")

        # Threshold check: L2 distance <= 0.12 corresponds to Cosine Similarity >= 0.95
        if distance <= 0.12:
            return {
                "plan_json": doc.metadata.get("plan_json", ""),
                "matched_question": doc.page_content,
                "distance": distance,
            }
    except Exception as e:
        print(f"[SQL Cache] Error checking cache: {e}")
    return None


def add_to_cache(question: str, plan_results: list):
    """Save a successful query's plan to the semantic cache."""
    if not plan_results:
        return
    try:
        store = get_cache_store()
        # Serialize only the plan: label, sub_question, sql, chart_type
        plan = []
        for block in plan_results:
            if block.get("status") == "success" and block.get("sql"):
                plan.append({
                    "label": block.get("label", ""),
                    "sub_question": block.get("sub_question", ""),
                    "sql": block.get("sql", ""),
                    "chart_type": block.get("chart_type", "none")
                })

        if not plan:
            return

        metadata = {
            "plan_json": json.dumps(plan),
        }

        doc = Document(
            page_content=question,
            metadata=metadata
        )
        store.add_documents([doc])
        print(f"[SQL Cache] Successfully cached query plan for: '{question}'")
    except Exception as e:
        print(f"[SQL Cache] Error caching query plan: {e}")


def execute_cached_sql(sql: str) -> list[dict]:
    """Execute cached SQL directly against target DB to get fresh rows."""
    engine = create_engine(TARGET_DB_URL)
    with engine.connect() as conn:
        cursor = conn.execute(sa_text(sql))
        columns = list(cursor.keys())
        raw_rows = cursor.fetchall()
        
        from .nodes.sql_runner import _safe_value
        result_rows = [
            {col: _safe_value(val) for col, val in zip(columns, row)}
            for row in raw_rows
        ]
    return result_rows
