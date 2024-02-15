from django.apps import AppConfig
import os


class OsuappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "osuapp"

    def ready(self):
        from .jobs import start_scheduler

        if os.environ.get("RUN_MAIN", None) != "true":
            start_scheduler()
