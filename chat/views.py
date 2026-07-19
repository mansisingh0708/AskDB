"""
chat/views.py
─────────────
Endpoints:
  GET  /             → redirect to /chat/
  GET  /chat/        → new conversation 
  GET  /chat/<id>/   → load a specific conversation
  POST /chat/ask/    → run agent, save messages, return JSON
  GET  /chat/history/→ list all conversations for this session
"""
import json
import time
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
# from django.views.decorators.csrf import csrf_exempt

from .models import Conversation, Message, QueryLog

# Link b/w the agentic ai part with the djago backend
from agent.graph import run_agent


## this both are just a helper function!
def _get_or_create_session(request):
    """Ensure every visitor has a session key."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _conversations_for_session(session_key):
    return Conversation.objects.filter(session_key=session_key).order_by("-created_at")



def index(request):
    return redirect("chat:chat")

def debug_logs(request):
    logs = list(QueryLog.objects.order_by("-id")[:10].values())
    return JsonResponse({"logs": logs})


def chat_view(request, conversation_id=None):
    session_key = _get_or_create_session(request)
    #on a specific convo..

    if conversation_id:
        conversation = get_object_or_404(
            Conversation, id=conversation_id, session_key=session_key
        )
    else:
        conversation = (
            _conversations_for_session(session_key).first()
            or Conversation.objects.create(session_key=session_key, title="New Chat")
        )

    messages = conversation.messages.all()
    conversations = _conversations_for_session(session_key)

    return render(
        request,
        "chat/chat.html",
        {
            "conversation": conversation,
            "messages": messages,
            "conversations": conversations,
        },
    )


def new_conversation(request):
    session_key = _get_or_create_session(request)
    conv = Conversation.objects.create(session_key=session_key, title="New Chat")
    return redirect("chat:chat_with_id", conversation_id=conv.id)


def history(request):
    session_key = _get_or_create_session(request)
    conversations = _conversations_for_session(session_key)
    return render(request, "chat/history.html", {"conversations": conversations})


@require_http_methods(["POST"])
def ask(request):
    """
    POST /chat/ask/
    Body (JSON): { "question": "...", "conversation_id": "..." }
    Returns JSON: { "answer": "...", "sql": "...", "chart_url": "...", "rows": [...] }
    """
    session_key = _get_or_create_session(request)

    try:
        body = json.loads(request.body)
        question = body.get("question", "").strip()
        conversation_id = body.get("conversation_id")

        # if not question:
        #     return JsonResponse({"error": "Question is required"}, status=400)

        # Get conversation
        conversation = Conversation.objects.get(
            id=conversation_id, session_key=session_key
        )

        # Set conversation title from first message
        if conversation.title == "New Chat":
            conversation.title = question[:80]
            conversation.save(update_fields=["title"])

        # Save user message
        user_msg = Message.objects.create(
            conversation=conversation,
            role="user",
            text=question,
        )

        # Build chat history from previous messages 
        previous_messages = conversation.messages.order_by("-created_at")[:10]
        chat_history = [
            {"role": msg.role, "text": msg.text}
            for msg in previous_messages
        ]
    except Exception as e:
        return JsonResponse({"error": f"Failed to initialize request: {str(e)}"}, status=400)

    # ── Run the agent ─────────────────────
    start_ms = int(time.time() * 1000)
    agent_res = {}
    try:
        agent_res = run_agent(question, chat_history=chat_history)
        elapsed_ms = int(time.time() * 1000) - start_ms

        executive_summary = agent_res.get("executive_summary", "")
        results = agent_res.get("results", [])
        cache_hit = agent_res.get("cache_hit", False)
        error_text = ""

    except Exception as e:
        elapsed_ms = int(time.time() * 1000) - start_ms
        executive_summary = f"Sorry, an error occurred: {str(e)}"
        results = []
        cache_hit = False
        error_text = str(e)

    # Convert chart_path -> chart_url for all blocks and sanitize rows
    import os
    from django.conf import settings
    for block in results:
        cp = block.get("chart_path", "")
        if cp:
            filename = os.path.basename(cp)
            block["chart_url"] = settings.MEDIA_URL + "charts/" + filename
        else:
            block["chart_url"] = ""
            
        # Serialize rows safely and cap at 50 to avoid DB bloat
        raw_rows = block.get("rows", [])
        safe_rows = []
        if isinstance(raw_rows, list):
            for row in raw_rows[:50]:
                if isinstance(row, dict):
                    safe_rows.append({k: str(v) for k, v in row.items()})
                elif isinstance(row, (list, tuple)):
                    safe_rows.append({f"col_{i}": str(v) for i, v in enumerate(row)})
        block["rows"] = safe_rows

    # If data and there is only 1 block, let's set executive_summary to that block's analysis if empty
    if results and not executive_summary:
        executive_summary = results[0].get("analysis", "")

    # Save assistant message
    assistant_msg = Message.objects.create(
        conversation=conversation,
        role="assistant",
        text=executive_summary,
        details_json=results,
    )
    # Save one QueryLog per block
    if results:
        for block in results:
            QueryLog.objects.create(
                message=assistant_msg,
                generated_sql=block.get("sql", ""),
                rows_returned=len(block.get("rows", [])),
                execution_ms=0,
                status=block.get("status", "failed"),
                error_text=block.get("error", "") or "",
            )
    elif error_text:
        QueryLog.objects.create(
            message=assistant_msg,
            generated_sql="",
            rows_returned=0,
            execution_ms=elapsed_ms,
            status="error",
            error_text=error_text,
        )

    # Add cache hit notice to executive summary if cache hit
    if cache_hit:
        executive_summary += "\n\n*(⚡ Note: Results retrieved instantly from semantic query cache)*"

    return JsonResponse(
        {
            "executive_summary": executive_summary,
            "results": results,
            "conversation_id": str(conversation.id),
            "execution_ms": elapsed_ms,
            "cache_hit": cache_hit,
        }
    )
