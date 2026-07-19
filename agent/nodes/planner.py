"""
agent/nodes/planner.py — Classifies the user's question and decomposes if needed.
"""
import json
import re
from ..prompts import PLANNER_PROMPT, SMALL_TALK_PROMPT
from ..config import get_llm

def planner(state: dict) -> dict:
    """
    LangGraph node: classify question and decompose into blocks.
    Updates state with:
      - route: "data" | "smalltalk"
      - results: list of dicts (each containing label, sub_question, and placeholder fields)
      - executive_summary: set if smalltalk (avoiding SQL step)
    """
    llm = get_llm(temperature=0)
    question = state["question"]
    chat_history = state.get("chat_history", [])

    # Build context from history
    context_question = question
    if chat_history:
        recent = chat_history[-4:]
        history_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['text'][:150]}"
            for m in recent
        )
        context_question = f"Conversation:\n{history_text}\n\nLatest message: {question}"

    # Classify & Decompose
    chain = PLANNER_PROMPT | llm
    response = chain.invoke({"question": context_question})
    content = response.content.strip()
    
    # Clean up markdown code block ticks if LLM wrapped it
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n|\n```$", "", content, flags=re.MULTILINE).strip()
        
    route = "data"
    results = []
    
    try:
        data = json.loads(content)
        route = data.get("route", "data").lower()
        if route == "data_query": # handle minor LLM alias variations
            route = "data"
        elif route == "small_talk":
            route = "smalltalk"
            
        results = data.get("results", [])
    except Exception as e:
        print(f"[Planner] Failed to parse JSON response: {e}. Falling back to single-query data route.")
        route = "data"
        results = [{
            "label": "Data Query",
            "sub_question": question
        }]
        
    if route == "smalltalk":
        # Generate the smalltalk response directly
        small_talk_input = question
        if chat_history:
            recent = chat_history[-6:]
            history_text = "\n".join(
                f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['text'][:200]}"
                for m in recent
            )
            small_talk_input = f"Conversation history:\n{history_text}\n\nUser's latest message: {question}"

        small_talk_chain = SMALL_TALK_PROMPT | llm
        st_response = small_talk_chain.invoke({"question": small_talk_input})
        return {
            "route": "smalltalk",
            "results": [],
            "executive_summary": st_response.content.strip()
        }
        
    # Ensure every block has empty/initial keys for downstream nodes to populate
    for block in results:
        block.setdefault("sql", "")
        block.setdefault("rows", [])
        block.setdefault("chart_path", "")
        block.setdefault("chart_type", "none")
        block.setdefault("analysis", "")
        block.setdefault("status", "pending")
        block.setdefault("error", "")

    return {
        "route": "data",
        "results": results,
        "executive_summary": ""
    }
