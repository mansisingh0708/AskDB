from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.index, name="index"),
    path("chat/", views.chat_view, name="chat"),
    path("chat/new/", views.new_conversation, name="new_conversation"),
    path("chat/<uuid:conversation_id>/", views.chat_view, name="chat_with_id"),
    path("chat/ask/", views.ask, name="ask"),
    path("chat/history/", views.history, name="history"),
    path("chat/debug/", views.debug_logs, name="debug_logs"),
]
