from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"

    def ready(self):
        import os
        # Only run on the main process (not the reloader process in dev mode)
        if os.environ.get('RUN_MAIN') == 'true':
            from django.core.management import call_command
            try:
                call_command('makemigrations', 'chat', interactive=False)
                call_command('migrate', interactive=False)
                print("[Chat Startup] Programmatic database migrations completed successfully.")
            except Exception as e:
                print(f"[Chat Startup] Programmatic migrations failed: {e}")
