from django.contrib import admin
from .models import Conversation, Message, QueryLog


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "session_key", "created_at"]
    search_fields = ["title", "session_key"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "role", "text_preview", "created_at"]
    list_filter = ["role"]
    search_fields = ["text"]

    def text_preview(self, obj):
        return obj.text[:60]
    text_preview.short_description = "Text"


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "rows_returned", "execution_ms", "created_at"]
    list_filter = ["status"]
    search_fields = ["generated_sql", "error_text"]
