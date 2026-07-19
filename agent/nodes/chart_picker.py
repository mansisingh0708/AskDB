"""
agent/nodes/chart_picker.py — Picks and renders charts from the results.

Interview talking point:
"I auto-detect chart type from result shape: single metric → big number,
 categorical groups → bar/pie, time series → line. Then I render a PNG
 with Matplotlib and return the file path."

Multi-chart support:
  When the agent runs multiple SQL queries for a compound question,
  this node generates a separate chart per result set.
"""
import os
import re
import uuid
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from ..config import CHARTS_DIR


# Ensure charts directory exists
Path(CHARTS_DIR).mkdir(parents=True, exist_ok=True)

# ── Chart styling ────────────────────────────────────────────────────────────
COLORS = [
    "#6366f1", "#8b5cf6", "#a855f7", "#d946ef",
    "#ec4899", "#f43f5e", "#f97316", "#eab308",
    "#22c55e", "#14b8a6", "#06b6d4", "#3b82f6",
]

plt.rcParams.update({
    "figure.facecolor": "#0f172a",
    "axes.facecolor": "#1e293b",
    "axes.edgecolor": "#334155",
    "text.color": "#e2e8f0",
    "axes.labelcolor": "#e2e8f0",
    "xtick.color": "#94a3b8",
    "ytick.color": "#94a3b8",
    "grid.color": "#334155",
    "grid.alpha": 0.5,
    "font.family": "sans-serif",
    "font.size": 11,
})


def _derive_label(sql: str, columns: list[str] = None) -> str:
    """Derive a short human-readable label from the SQL query and result columns."""
    sql_upper = sql.upper()

    # Try to extract aliased columns to understand what was selected
    # e.g. SUM(order_total) AS total_revenue → "Revenue"
    alias_match = re.findall(r'AS\s+(\w+)', sql, re.IGNORECASE)
    meaningful_aliases = [a for a in alias_match
                         if a.lower() not in ('p', 'o', 'oi', 'c', 'month', 'name')]

    # Try to extract ALL table names (including JOINed)
    tables = re.findall(r'(?:FROM|JOIN)\s+(\w+)', sql_upper)
    unique_tables = []
    seen_t = set()
    for t in tables:
        tl = t.lower()
        if tl not in seen_t:
            seen_t.add(tl)
            unique_tables.append(t.title().replace('_', ' '))

    # Detect aggregation type
    if 'COUNT(' in sql_upper:
        action = 'Count'
    elif 'SUM(' in sql_upper:
        action = 'Total'
    elif 'AVG(' in sql_upper:
        action = 'Average'
    elif 'GROUP BY' in sql_upper:
        action = 'Breakdown'
    elif 'ORDER BY' in sql_upper and 'LIMIT' in sql_upper:
        action = 'Top'
    elif len(tables) > 1:
        action = 'Details'
    else:
        action = 'Results'

    # Build a descriptive label
    if meaningful_aliases:
        # e.g. "Total: total_quantity, revenue" → "Total: Quantity & Revenue"
        alias_label = ', '.join(
            a.replace('_', ' ').title() for a in meaningful_aliases[:3]
        )
        table_label = ' & '.join(unique_tables[:2]) if unique_tables else 'Query'
        return f"{action}: {alias_label} ({table_label})"

    table_label = ' & '.join(unique_tables[:2]) if unique_tables else 'Query'
    return f"{action} — {table_label}"


def _detect_chart_type(data: list[dict], sub_question: str = "") -> str:
    """
    Heuristic chart type detection:
      - 1 row, 1 value column → big_number (no chart)
      - Datetime-like label column → line
      - ≤ 6 categories AND composition intent → pie
      - Otherwise → bar
    """
    if not data or not isinstance(data, list):
        return "none"

    if len(data) == 1:
        values = list(data[0].values())
        # Single scalar result
        if len(values) <= 2:
            return "big_number"

    if len(data) > 50:
        return "bar"

    # Check if first column looks like a date
    first_row = data[0]
    keys = list(first_row.keys())
    if keys:
        first_val = str(first_row[keys[0]]).lower()
        date_indicators = ["2024", "2025", "2026", "jan", "feb", "mar", "apr",
                           "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
                           "q1", "q2", "q3", "q4"]
        if any(ind in first_val for ind in date_indicators):
            return "line"

    # Only choose pie if this is a composition query containing specific breakdown words
    q_lower = sub_question.lower()
    composition_words = ["share", "percent", "pct", "breakdown", "distribution", "proportion", "ratio", "split"]
    is_composition = any(word in q_lower for word in composition_words)

    if len(data) <= 6 and is_composition:
        return "pie"

    return "bar"


def _find_columns(data: list[dict], sql: str = "") -> tuple[str, str]:
    """Find the best label column and value column from data.
    
    Skips ID columns for labels. Prefers text columns over numeric for labels.
    Uses the last numeric non-ID column as the value.
    """
    keys = list(data[0].keys())
    
    # Identify which columns are numeric vs text
    id_patterns = ('_id', 'id')
    
    def is_id_col(col_name: str) -> bool:
        cl = col_name.lower()
        return cl.endswith('_id') or cl == 'id'
    
    def is_numeric(val) -> bool:
        try:
            float(val)
            return True
        except (ValueError, TypeError):
            return False

    # 1. Try to find the value column using ORDER BY first
    if sql:
        sql_clean = re.sub(r'\s+', ' ', sql.lower())
        match = re.search(r'order\s+by\s+([\w\.\`\s\(\)\,\-\*\/]+?)(?:limit|;|offset|$)', sql_clean)
        if match:
            order_clause = match.group(1).strip()
            for key in keys:
                key_clean = key.lower().strip('`').strip('"')
                if re.search(r'\b' + re.escape(key_clean) + r'\b', order_clause):
                    if is_numeric(data[0].get(key)) and not is_id_col(key):
                        value_col = key
                        
                        # Find the best label column (first non-ID, non-value column)
                        label_col = keys[0]
                        for k in keys:
                            if k == value_col:
                                continue
                            if not is_id_col(k) and not is_numeric(data[0].get(k)):
                                label_col = k
                                break
                        else:
                            for k in keys:
                                if k != value_col and not is_id_col(k):
                                    label_col = k
                                    break
                                    
                        return label_col, value_col
    
    # 2. Fallback to default heuristic if ORDER BY doesn't yield a match
    # Find the best value column (last numeric, non-ID)
    value_col = keys[-1]
    for k in reversed(keys):
        if is_numeric(data[0].get(k)) and not is_id_col(k):
            value_col = k
            break
    
    # Find the best label column:
    # Priority: text column that's not an ID > any non-value column
    label_col = keys[0]
    # First pass: look for a text (non-numeric, non-ID) column
    for k in keys:
        if k == value_col:
            continue
        if not is_id_col(k) and not is_numeric(data[0].get(k)):
            label_col = k
            break
    else:
        # Second pass: any non-value, non-ID column
        for k in keys:
            if k != value_col and not is_id_col(k):
                label_col = k
                break
        else:
            # Last resort: first column that isn't the value
            for k in keys:
                if k != value_col:
                    label_col = k
                    break

    return label_col, value_col


def _render_bar(data: list[dict], question: str, sql: str = "") -> str:
    """Render a bar chart and return the file path."""
    label_col, value_col = _find_columns(data, sql)
    # sort bars by value descending so the chart is readable
    # regardless of whether the SQL had an ORDER BY
    data = sorted(data, key=lambda r: float(r[value_col]), reverse=True)
    labels = [str(row[label_col]) for row in data]
    values = [float(row[value_col]) for row in data]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(range(len(labels)), values, color=COLORS[:len(labels)], 
                  width=0.6, edgecolor="none", alpha=0.9)

    # Add value labels on bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                f"{val:,.0f}", ha="center", va="bottom", fontsize=10, color="#e2e8f0")

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_title(question[:80], fontsize=13, pad=15, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--")

    path = os.path.join(CHARTS_DIR, f"chart_{uuid.uuid4().hex[:8]}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _render_line(data: list[dict], question: str, sql: str = "") -> str:
    """Render a line chart and return the file path."""
    label_col, value_col = _find_columns(data, sql)
    labels = [str(row[label_col]) for row in data]
    values = [float(row[value_col]) for row in data]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(range(len(labels)), values, color=COLORS[0], linewidth=2.5, marker="o",
            markerfacecolor=COLORS[1], markeredgecolor="#0f172a", markersize=8)
    ax.fill_between(range(len(labels)), values, alpha=0.15, color=COLORS[0])

    ax.set_title(question[:80], fontsize=13, pad=15, fontweight="bold")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--")

    path = os.path.join(CHARTS_DIR, f"chart_{uuid.uuid4().hex[:8]}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _render_pie(data: list[dict], question: str, sql: str = "") -> str:
    """Render a pie chart and return the file path."""
    label_col, value_col = _find_columns(data, sql)
    labels = [str(row[label_col]) for row in data]
    values = [float(row[value_col]) for row in data]

    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=COLORS[:len(labels)],
        autopct="%1.1f%%", startangle=140,
        textprops={"color": "#e2e8f0", "fontsize": 11},
        wedgeprops={"edgecolor": "#0f172a", "linewidth": 2},
    )
    for autotext in autotexts:
        autotext.set_fontsize(10)
        autotext.set_fontweight("bold")

    ax.set_title(question[:80], fontsize=13, pad=20, fontweight="bold")

    path = os.path.join(CHARTS_DIR, f"chart_{uuid.uuid4().hex[:8]}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _render_single(data: list[dict], title: str, sql: str = "", sub_question: str = "") -> dict:
    """Render a single chart for one result set. Returns {chart_path, chart_type}.
    
    Skips chart generation for "detail" tables:
      - Tables with 4+ columns (they're join results, not summaries)
      - Tables where the label column has >30% duplicate values
      - Tables where all labels are numeric (IDs)
    """
    if not data or not isinstance(data, list):
        return {"chart_path": "", "chart_type": "none"}

    keys = list(data[0].keys())
    num_cols = len(keys)

    # Check if data has at least one numeric non-ID column
    has_chartable_numeric = False
    for k, v in data[0].items():
        if k.lower().endswith('_id') or k.lower() == 'id':
            continue
        try:
            float(v)
            has_chartable_numeric = True
            break
        except (ValueError, TypeError):
            continue

    if not has_chartable_numeric:
        print(f"[AskDB Chart] Skipping chart: no chartable numeric column")
        return {"chart_path": "", "chart_type": "none"}

    # Skip chart for wide detail tables (4+ columns = likely a JOIN result)
    if num_cols >= 4 and len(data) > 6:
        print(f"[AskDB Chart] Skipping chart: detail table ({num_cols} cols, {len(data)} rows)")
        return {"chart_path": "", "chart_type": "none"}

    # Check label quality
    label_col, value_col = _find_columns(data, sql)
    labels = [str(row.get(label_col, '')) for row in data]

    # Skip if >30% of labels are duplicates
    unique_labels = set(labels)
    if len(labels) > 3 and len(unique_labels) < len(labels) * 0.7:
        print(f"[AskDB Chart] Skipping chart: too many duplicate labels ({len(unique_labels)}/{len(labels)} unique)")
        return {"chart_path": "", "chart_type": "none"}

    # Skip if all labels are numeric (likely IDs), but allow dates/years
    def is_just_id(lbl):
        if not lbl: return False
        # If it contains dashes or slashes, it might be a date (e.g. 2026-06)
        if '-' in lbl or '/' in lbl: return False
        lbl_clean = lbl.replace('.', '')
        # Only treat as ID if it's purely digits and not a recent year (like 2024)
        if lbl_clean.isdigit():
            # If it looks like a year, keep it
            if len(lbl_clean) == 4 and 1900 <= int(lbl_clean) <= 2100:
                return False
            return True
        return False
        
    all_numeric_labels = all(is_just_id(label) for label in labels if label)
    if all_numeric_labels and len(labels) > 3:
        print(f"[AskDB Chart] Skipping chart: all labels are numeric (IDs)")
        return {"chart_path": "", "chart_type": "none"}

    chart_type = _detect_chart_type(data, sub_question)
    if chart_type in ("none", "big_number"):
        return {"chart_path": "", "chart_type": chart_type}

    renderers = {
        "bar": _render_bar,
        "line": _render_line,
        "pie": _render_pie,
    }
    renderer = renderers.get(chart_type, _render_bar)
    chart_path = renderer(data, title, sql)
    return {"chart_path": chart_path, "chart_type": chart_type}


def chart_picker(state: dict) -> dict:
    """
    LangGraph node: pick chart types and render PNGs per block in `results`.
    """
    results = state.get("results", [])
    route = state.get("route", "")

    if route != "data" or not results:
        return {}

    updated_results = []
    for block in results:
        new_block = dict(block)
        rows = new_block.get("rows", [])
        
        if new_block.get("status") == "success" and rows:
            try:
                chart_info = _render_single(
                    rows, 
                    new_block.get("label", "Chart"),
                    sql=new_block.get("sql", ""),
                    sub_question=new_block.get("sub_question", "")
                )
                new_block["chart_path"] = chart_info.get("chart_path", "")
                new_block["chart_type"] = chart_info.get("chart_type", "none")
            except Exception as e:
                print(f"[Chart Picker] Chart generation failed for block '{new_block['label']}': {e}")
                new_block["chart_path"] = ""
                new_block["chart_type"] = "error"
        else:
            new_block["chart_path"] = ""
            new_block["chart_type"] = "none"
            
        updated_results.append(new_block)

    return {"results": updated_results}
