import mimetypes

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Core"

    def ready(self):
        # Not every platform ships these in its mime database.
        mimetypes.add_type("image/webp", ".webp")
        mimetypes.add_type("image/avif", ".avif")
        mimetypes.add_type("image/svg+xml", ".svg")
