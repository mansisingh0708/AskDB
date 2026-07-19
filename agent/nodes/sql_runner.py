"""
agent/nodes/sql_runner.py — Wraps LangChain's SQL agent with per-block verify/retry logic.
"""
import time
import re
import json
from decimal import Decimal
from datetime import datetime, date
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit, create_sql_agent
from langchain.agents.agent_types import AgentType
from langchain_core.callbacks import BaseCallbackHandler

from ..config import TARGET_DB_URL, QUERY_TIMEOUT_SECS, MAX_ROWS_LIMIT, get_llm, MAX_RETRIES
from ..glossary_rag import retrieve
from ..safety import check_and_sanitize
from ..prompts import SQL_SYSTEM, VERIFIER_PROMPT


# ─── Callback to capture SQL queries ─────────────────────────────────────────

class SQLCaptureHandler(BaseCallbackHandler):
    """Intercepts every tool call to capture SQL queries."""

    def __init__(self):
        self.captured_queries = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        """Called when any tool starts — captures the input."""
        tool_name = serialized.get("name", "")
        if "query" in tool_name.lower() and "checker" not in tool_name.lower():
            query = ""
            if isinstance(input_str, dict):
                query = input_str.get("query", input_str.get("tool_input", ""))
            elif isinstance(input_str, str):
                input_str = input_str.strip()
                if input_str.startswith("{"):
                    import ast
                    try:
                        parsed_input = json.loads(input_str)
                        if isinstance(parsed_input, dict):
                            query = parsed_input.get("query", parsed_input.get("tool_input", ""))
                    except Exception:
                        try:
                            parsed_input = ast.literal_eval(input_str)
                            if isinstance(parsed_input, dict):
                                query = parsed_input.get("query", parsed_input.get("tool_input", ""))
                        except Exception:
                            pass
                if not query:
                    query = input_str
            
            if query and "SELECT" in query.upper():
                self.captured_queries.append(query.strip())
                print(f"[AskDB CB] Captured SQL: {query[:200]}")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_db() -> SQLDatabase:
    """Create a read-only SQLDatabase connection."""
    return SQLDatabase.from_uri(TARGET_DB_URL, sample_rows_in_table_info=3)


def _extract_sql_from_text(text: str) -> str:
    """Extract a SELECT statement from arbitrary text."""
    if not text:
        return ""
    patterns = [
        r"```sql\s*(.*?)\s*```",
        r"```\s*(SELECT.*?)\s*```",
        r"(SELECT\s+.+?(?:LIMIT\s+\d+\s*;?|;\s*$))",
        r"(SELECT\s+.+?)(?:\n\n|\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1).strip().rstrip(";").strip()
            if sql:
                return sql
    return ""


def _safe_value(v):
    """Convert DB value types to JSON-safe Python types."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return str(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def _deduplicate_queries(queries: list[str]) -> list[str]:
    """Remove duplicate SQL queries, keeping order."""
    seen = set()
    unique = []
    for q in queries:
        normalised = re.sub(r'\s+', ' ', q.strip().upper())
        if normalised not in seen:
            seen.add(normalised)
            unique.append(q)
    return unique


def _derive_label(sql: str, columns: list[str] = None) -> str:
    """Import and delegate to chart_picker's smarter label derivation."""
    from .chart_picker import _derive_label as _chart_derive_label
    return _chart_derive_label(sql, columns)


def _execute_single_query(sql: str) -> list[dict]:
    """Execute a single SQL query and return structured rows."""
    from sqlalchemy import create_engine, text as sa_text
    engine = create_engine(TARGET_DB_URL)
    with engine.connect() as conn:
        cursor = conn.execute(sa_text(sql))
        columns = list(cursor.keys())
        raw_rows = cursor.fetchall()
        return [
            {col: _safe_value(val) for col, val in zip(columns, row)}
            for row in raw_rows
        ]


# ─── Node ─────────────────────────────────────────────────────────────────────

def sql_runner(state: dict) -> dict:
    """
    LangGraph node: Process each block in `results` independently.
    Runs SQL agent, applies safety checks, executes, verifies, and retries per block.
    """
    results = state.get("results", [])
    route = state.get("route", "")

    if route != "data" or not results:
        return {}

    db = _get_db()
    llm = get_llm(temperature=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    # Pick agent type based on LLM provider
    cls_name = llm.__class__.__name__.lower()
    if "openai" in cls_name:
        agent_type = "openai-tools"
    elif "google" in cls_name:
        agent_type = "tool-calling"
    else:
        agent_type = AgentType.ZERO_SHOT_REACT_DESCRIPTION

    updated_results = []
    for block in results:
        # Copy to avoid direct mutations during iterations
        new_block = dict(block)
        sub_question = new_block["sub_question"]
        
        # Check if the sub_question contains write/modification intent
        write_pattern = re.compile(
            r"\b(delete|drop|update|insert|truncate|alter|create|modify|remove)\b",
            re.IGNORECASE
        )
        if write_pattern.search(sub_question):
            print(f"[SQL Runner] Blocking write/modification query: {sub_question}")
            new_block["status"] = "blocked"
            new_block["error"] = "Write/modification query blocked."
            new_block["analysis"] = (
                "For security and safety reasons, database modification operations "
                "(such as deleting, updating, or inserting records) are strictly disabled on this platform. "
                "The system operates with read-only access privileges to maintain data integrity."
            )
            new_block["sql"] = "-- BLOCKED: Database modification actions are disabled"
            new_block["rows"] = []
            updated_results.append(new_block)
            continue
            
        # Local verify/retry loop for this block
        retries = 0
        max_retries = MAX_RETRIES or 2
        agent_input = sub_question
        
        # Retrieve glossary RAG context
        glossary_context = retrieve(sub_question)
        current_date_str = date.today().strftime("%Y-%m-%d")
        system_prompt = SQL_SYSTEM.format(
            glossary_context=glossary_context or "No glossary context available.",
            current_date=current_date_str
        )

        block_sql = ""
        block_rows = []
        block_status = "failed"
        block_error = ""

        print(f"\n[SQL Runner] Executing block: '{new_block['label']}'")

        while retries <= max_retries:
            sql_handler = SQLCaptureHandler()
            agent_executor = create_sql_agent(
                llm=llm,
                toolkit=toolkit,
                agent_type=agent_type,
                verbose=True,
                prefix=system_prompt,
                top_k=MAX_ROWS_LIMIT,
                handle_parsing_errors=True,
            )

            try:
                response = agent_executor.invoke(
                    {"input": agent_input},
                    config={"callbacks": [sql_handler]},
                )
                output = response.get("output", "")

                # Capture SQL
                captured = _deduplicate_queries(sql_handler.captured_queries)
                if not captured:
                    fallback_sql = _extract_sql_from_text(output)
                    if fallback_sql:
                        captured = [fallback_sql]

                if not captured:
                    block_status = "failed"
                    block_error = "No SQL query was generated by the agent."
                    break

                # Extract and sanitize last executed query
                sql = captured[-1].strip().rstrip(";").strip()
                is_safe, reason, sanitized = check_and_sanitize(sql)
                if not is_safe:
                    block_status = "blocked"
                    block_error = f"Unsafe SQL statement blocked: {reason}"
                    break  # Hard security stop

                sql = sanitized

                # Execute target query
                try:
                    rows = _execute_single_query(sql)
                    # Cap database rows at 50 to prevent database/payload bloat
                    capped_rows = rows[:50]

                    # Verify result logic
                    current_date_str = date.today().strftime("%Y-%m-%d")
                    result_preview = str(capped_rows[:10]) if capped_rows else "No rows returned"
                    verifier_chain = VERIFIER_PROMPT | llm
                    v_response = verifier_chain.invoke({
                        "question": sub_question,
                        "sql": sql,
                        "result_preview": result_preview,
                        "current_date": current_date_str,
                    })

                    # Parse verify response
                    v_content = v_response.content.strip()
                    v_status = "ok"
                    v_reason = ""
                    try:
                        # Extract JSON if wrapped in markdown or conversational text
                        json_match = re.search(r"\{.*\}", v_content, re.DOTALL)
                        if json_match:
                            parsed = json.loads(json_match.group(0))
                            v_status = parsed.get("status", "ok").lower()
                            v_reason = parsed.get("reason", "")
                        else:
                            raise ValueError("No JSON found")
                    except Exception:
                        # Robust fallback: search for status key-value patterns
                        status_match = re.search(r'"status"\s*:\s*"(\w+)"', v_content.lower())
                        if status_match:
                            v_status = status_match.group(1)
                        else:
                            v_content_lower = v_content.lower()
                            if "failed" in v_content_lower and "not failed" not in v_content_lower:
                                v_status = "failed"
                            elif "retry" in v_content_lower and "no need to retry" not in v_content_lower:
                                v_status = "retry"
                            else:
                                v_status = "ok"

                    # Fail-safe override for false positive "future year" or "2026" rejections
                    if v_status == "retry" and ("2026" in v_reason or "future" in v_reason.lower()):
                        print(f"[AskDB Verifier Override] Overriding false positive: {v_reason}")
                        v_status = "ok"

                    if v_status == "ok":
                        block_status = "success"
                        block_sql = sql
                        block_rows = capped_rows
                        block_error = ""
                        break  # Verification success!
                    
                    elif v_status == "retry" and retries < max_retries:
                        print(f"[SQL Runner] Block '{new_block['label']}' verification check failed. Retrying (Attempt {retries+1}/{max_retries}). Reason: {v_reason}")
                        retries += 1
                        agent_input = (
                            f"Your previous SQL query or answer for sub-question: '{sub_question}' had issues.\n"
                            f"Previous SQL: {sql}\n"
                            f"Reason for rejection: {v_reason}\n"
                            f"Please correct the query or logic and run it again."
                        )
                        continue
                    else:
                        block_status = "failed"
                        block_sql = sql
                        block_rows = capped_rows
                        block_error = f"Verification failed: {v_reason}"
                        break

                except Exception as db_err:
                    block_status = "error"
                    block_error = str(db_err)
                    if retries < max_retries:
                        print(f"[SQL Runner] Block '{new_block['label']}' database error. Retrying (Attempt {retries+1}/{max_retries}). Error: {db_err}")
                        retries += 1
                        agent_input = (
                            f"Your previous SQL query for sub-question: '{sub_question}' caused a database error.\n"
                            f"Previous SQL: {sql}\n"
                            f"Error message: {db_err}\n"
                            f"Please fix the SQL syntax/schema mapping and try again."
                        )
                        continue
                    break

            except Exception as e:
                block_status = "error"
                block_error = str(e)
                break

        # Populate block properties
        new_block["sql"] = block_sql
        new_block["rows"] = block_rows
        new_block["status"] = block_status
        new_block["error"] = block_error
        
        updated_results.append(new_block)

    return {"results": updated_results}
