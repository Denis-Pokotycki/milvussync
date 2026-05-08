import os
from django.apps import AppConfig


class SyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sync"

    def ready(self):
        import sys
        # Django dev server runs ready() in both the auto-reloader parent process
        # (file watcher, RUN_MAIN not set) and the child process (actual server,
        # RUN_MAIN=true). Only start the background thread in the real server process.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        from django.conf import settings
        if not getattr(settings, "AUTO_SYNC_ENABLED", True):
            return

        from sync.autosync import start
        start(
            interval=getattr(settings, "AUTO_SYNC_INTERVAL_SECONDS", 10),
            state_path=settings.SYNC_STATE_FILE,
        )
