"""
agent/safety.py — SQL guardrails (first line of defense).

Interview talking point:
"I parse every SQL statement with sqlglot's AST before execution.
 This catches dangerous statements (DELETE, DROP, etc.) and enforces a
 row LIMIT. The database user has SELECT-only privileges as the second line."
"""
import re
import sqlglot
from sqlglot import exp
from typing import Tuple

# Blocked statement types
BLOCKED_TYPES = (
    exp.Delete,
    exp.Drop,
    exp.Update,
    exp.Insert,
    exp.Alter,
    exp.Create,
    exp.Command,   # catches raw DDL like EXEC
)

# Blocked keywords (regex fallback for edge cases)
BLOCKED_PATTERNS = re.compile(
    r"\b(DELETE|DROP|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|EXEC|EXECUTE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

MAX_LIMIT = 1000


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Returns (is_safe: bool, reason: str).
    Safe means: only SELECT, and has a LIMIT ≤ MAX_LIMIT.
    """
    if not sql or not sql.strip():
        return False, "Empty SQL statement."

    # ── Step 1: AST-level check ───────────────────────────────────────────
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
    except Exception as e:
        # If we can't parse it, reject it
        return False, f"SQL parse error: {e}"

    # Walk every node in the AST and check for blocked types
    for node in parsed.walk():
        if isinstance(node, BLOCKED_TYPES):
            return False, f"Unsafe statement detected: {type(node).__name__}"

    # ── Step 2: Regex fallback (handles obfuscated / multi-statement) ─────
    if BLOCKED_PATTERNS.search(sql):
        return False, "Blocked keyword detected in SQL."

    # ── Step 3: Must be a SELECT ──────────────────────────────────────────
    if not isinstance(parsed, exp.Select):
        return False, "Only SELECT statements are allowed."

    return True, "OK"


def enforce_limit(sql: str, max_rows: int = MAX_LIMIT) -> str:
    """
    If the SQL has no LIMIT clause, inject LIMIT <max_rows>.
    If it has a LIMIT that exceeds max_rows, cap it.
    """
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
    except Exception:
        # Can't parse — append LIMIT as a string fallback
        if "LIMIT" not in sql.upper():
            return sql.rstrip(";") + f" LIMIT {max_rows}"
        return sql

    limit_node = parsed.find(exp.Limit)
    if limit_node is None:
        # No LIMIT — add one
        parsed = parsed.limit(max_rows)
    else:
        try:
            current_limit = int(limit_node.expression.this)
            if current_limit > max_rows:
                parsed = parsed.limit(max_rows)
        except (AttributeError, ValueError):
            pass  # Can't read the limit value — leave it

    return parsed.sql(dialect="mysql")


def check_and_sanitize(sql: str, max_rows: int = MAX_LIMIT) -> Tuple[bool, str, str]:
    """
    Full pipeline: validate then enforce limit.
    Returns (is_safe, reason, sanitized_sql).
    """
    is_safe, reason = validate_sql(sql)
    if not is_safe:
        return False, reason, sql

    sanitized = enforce_limit(sql, max_rows)
    return True, "OK", sanitized
