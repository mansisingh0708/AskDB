"""
agent/nodes/summary_generator.py — LangGraph node to write a global executive summary.
"""
from ..prompts import SUMMARY_PROMPT
from ..config import get_llm

def summary_generator(state: dict) -> dict:
    """
    LangGraph node: generate a cohesive executive summary from all block analyses and results.
    """
    route = state.get("route", "")
    results = state.get("results", [])

    if route != "data" or not results:
        return {"executive_summary": ""}

    # Gather data from all blocks
    analyses_list = []
    for i, block in enumerate(results):
        label = block.get("label", f"Query {i+1}")
        sub_q = block.get("sub_question", "")
        analysis = block.get("analysis", "")
        rows_preview = str(block.get("rows", []))[:1000] # Cap rows context
        
        block_text = (
            f"Block: {label}\n"
            f"Question: {sub_q}\n"
            f"Takeaway analysis: {analysis}\n"
            f"Data preview: {rows_preview}"
        )
        analyses_list.append(block_text)

    analyses = "\n\n====================\n\n".join(analyses_list)
    question = state.get("question", "")

    try:
        # Qualitative business synthesis
        llm = get_llm(temperature=0.3)
        chain = SUMMARY_PROMPT | llm
        response = chain.invoke({
            "question": question,
            "analyses": analyses,
        })
        summary = response.content.strip()
        print(f"[AskDB Summary] Generated executive summary:\n{summary}")
        return {"executive_summary": summary}
    except Exception as e:
        print(f"[AskDB Summary] Summary generation failed: {e}")
        return {"executive_summary": ""}
