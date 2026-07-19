"""
agent/graph.py — LangGraph state machine for AskDB v2 (independent results blocks).
"""
from typing import TypedDict
import time
import json
from langgraph.graph import StateGraph, END

from .nodes.planner import planner
from .nodes.sql_runner import sql_runner
from .nodes.chart_picker import chart_picker


# ─── State Schema ────────────────────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    """Typed state flowing through the graph."""
    question: str
    chat_history: list
    route: str            # "data" | "smalltalk"
    results: list         # each block: label, sub_question, sql, rows,
                          #             chart_path, chart_type, analysis, status, error
    executive_summary: str
    error: str
    execution_ms: int


# ─── Routing functions ───────────────────────────────────────────────────────

def route_after_planner(state: AgentState) -> str:
    """Route based on intent: data → SQL runner, smalltalk → done."""
    if state.get("route") == "data":
        return "sql_runner"
    return END


# ─── Build the graph ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct and compile the LangGraph v2 workflow."""
    from .nodes.analyst import analyst
    from .nodes.summary_generator import summary_generator
    
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner)
    graph.add_node("sql_runner", sql_runner)
    graph.add_node("chart_picker", chart_picker)
    graph.add_node("analyst", analyst)
    graph.add_node("summary_generator", summary_generator)

    # Set entry point
    graph.set_entry_point("planner")

    # Conditional edges
    graph.add_conditional_edges("planner", route_after_planner, {
        "sql_runner": "sql_runner",
        END: END,
    })

    # Linear workflow steps for data queries
    graph.add_edge("sql_runner", "chart_picker")
    graph.add_edge("chart_picker", "analyst")
    graph.add_edge("analyst", "summary_generator")
    graph.add_edge("summary_generator", END)

    return graph.compile()


# Singleton compiled graph
_compiled_graph = None


def get_graph():
    """Lazy singleton for the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ─── Public API ──────────────────────────────────────────────────────────────

def run_agent(question: str, chat_history: list = None) -> dict:
    """
    Run the v2 agent pipeline on a question.
    Checks the semantic cache first; if matched, executes cached SQL directly.

    Args:
        question: The user's current question.
        chat_history: List of previous messages [{"role": ..., "text": ...}].

    Returns dict with: executive_summary, results, execution_ms, cache_hit
    """
    from .query_cache import check_cache, execute_cached_sql, add_to_cache

    start_time = time.time()

    # 1. Check semantic plan cache
    cached = check_cache(question)
    if cached:
        try:
            print(f"[AskDB Agent] Cache HIT for: '{question}'. Re-running plan.")
            plan_json = cached.get("plan_json", "")
            results = []
            if plan_json:
                results = json.loads(plan_json)

            if results:
                # Re-execute cached queries to get fresh data
                for block in results:
                    sql = block.get("sql", "")
                    if sql:
                        try:
                            rows = execute_cached_sql(sql)
                            block["rows"] = rows[:50]  # Cap rows
                            block["status"] = "success"
                            block["error"] = ""
                        except Exception as e:
                            block["rows"] = []
                            block["status"] = "error"
                            block["error"] = str(e)

                # Re-generate charts
                from .nodes.chart_picker import chart_picker
                chart_state = {"route": "data", "results": results}
                chart_res = chart_picker(chart_state)
                results = chart_res.get("results", results)

                # Re-generate analyses
                from .nodes.analyst import analyst
                analyst_state = {"route": "data", "results": results}
                analyst_res = analyst(analyst_state)
                results = analyst_res.get("results", results)

                # Re-generate global executive summary
                from .nodes.summary_generator import summary_generator
                summary_state = {
                    "route": "data",
                    "results": results,
                    "question": question
                }
                summary_res = summary_generator(summary_state)
                executive_summary = summary_res.get("executive_summary", "")

                elapsed_ms = int((time.time() - start_time) * 1000)

                return {
                    "executive_summary": executive_summary,
                    "results": results,
                    "execution_ms": elapsed_ms,
                    "cache_hit": True
                }
        except Exception as e:
            print(f"[AskDB Agent] Failed to run cached plan: {e}. Falling back to full agent pipeline.")

    # 2. Cache miss -> run full LangGraph agent
    graph = get_graph()

    initial_state: AgentState = {
        "question": question,
        "chat_history": chat_history or [],
        "route": "",
        "results": [],
        "executive_summary": "",
        "error": "",
        "execution_ms": 0,
    }

    final_state = graph.invoke(initial_state)
    elapsed_ms = int((time.time() - start_time) * 1000)

    results = final_state.get("results", [])
    executive_summary = final_state.get("executive_summary", "")
    error = final_state.get("error", "")

    # 3. Cache successful plan
    any_success = any(block.get("status") == "success" for block in results)
    if any_success and final_state.get("route") == "data" and not error:
        add_to_cache(question, results)

    return {
        "executive_summary": executive_summary,
        "results": results,
        "execution_ms": elapsed_ms,
        "cache_hit": False,
    }
