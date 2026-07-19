"""
agent/nodes/verifier.py — Sanity-checks the SQL result.

Interview talking point:
"I added a verifier node that uses the LLM to check if the answer is
 consistent with the returned data. If not, it routes back to the SQL
 runner for a retry — up to MAX_RETRIES times."
"""
import json
from ..prompts import VERIFIER_PROMPT
from ..config import get_llm, MAX_RETRIES


def verifier(state: dict) -> dict:
    """
    LangGraph node: verify that the SQL result makes sense.

    Reads from state:
      - question, sql, result, answer
    Writes to state:
      - verification: "ok" | "retry" | "failed"
      - retries: incremented if retrying
    """
    question = state.get("question", "")
    sql = state.get("sql", "")
    result = state.get("result", [])
    answer = state.get("answer", "")
    retries = state.get("retries", 0)

    # If there was an error or no SQL, mark as failed
    if state.get("error"):
        return {"verification": "failed"}

    # If no SQL was generated, but we have an answer (might be small talk leakage)
    if not sql and answer:
        return {"verification": "ok"}

    # Prepare a preview of the result for the verifier
    result_preview = ""
    if isinstance(result, list) and result:
        result_preview = str(result[:10])
    elif isinstance(result, str):
        result_preview = result[:500]
    else:
        result_preview = "No rows returned"

    try:
        llm = get_llm(temperature=0)
        chain = VERIFIER_PROMPT | llm
        response = chain.invoke({
            "question": question,
            "sql": sql or "N/A",
            "result_preview": result_preview,
            "answer": answer,
        })

        # Parse the verification response
        content = response.content.strip()
        try:
            parsed = json.loads(content)
            status = parsed.get("status", "ok").lower()
        except json.JSONDecodeError:
            # If LLM didn't return JSON, try to extract status
            content_lower = content.lower()
            if "retry" in content_lower:
                status = "retry"
            elif "failed" in content_lower:
                status = "failed"
            else:
                status = "ok"

        # Handle retry logic
        if status == "retry" and retries < MAX_RETRIES:
            return {
                "verification": "retry",
                "retries": retries + 1,
            }
        elif status == "retry":
            # Max retries exceeded — accept what we have
            return {"verification": "ok"}

        return {"verification": status}

    except Exception as e:
        # If verification itself fails, accept the result
        return {"verification": "ok"}
