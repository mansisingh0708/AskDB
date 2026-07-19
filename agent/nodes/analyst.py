"""
agent/nodes/analyst.py — Generates a one-sentence analysis for each query result block.
"""
from ..prompts import ANALYST_PROMPT
from ..config import get_llm

def analyst(state: dict) -> dict:
    """
    LangGraph node: analyze the results of each query block.
    Fills the `analysis` field of each block in `results`.
    """
    results = state.get("results", [])
    route = state.get("route", "")
    
    if route != "data" or not results:
        return {}
        
    llm = get_llm(temperature=0)
    analyst_chain = ANALYST_PROMPT | llm
    
    updated_results = []
    for block in results:
        new_block = dict(block)
        
        # Only analyze successful blocks with data
        if new_block.get("status") == "success" and new_block.get("rows"):
            try:
                # Cap the rows for context window efficiency
                rows_preview = new_block["rows"][:10]
                response = analyst_chain.invoke({
                    "sub_question": new_block.get("sub_question", ""),
                    "sql": new_block.get("sql", ""),
                    "rows": str(rows_preview)
                })
                new_block["analysis"] = response.content.strip()
            except Exception as e:
                new_block["analysis"] = f"Failed to analyze: {e}"
        else:
            if not new_block.get("analysis"):
                new_block["analysis"] = ""
            
        updated_results.append(new_block)
        
    return {"results": updated_results}
