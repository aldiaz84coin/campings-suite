from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CampingsConfig(AppConfig):
    name = "campings"
    verbose_name = _("Campings")

    def ready(self):
        from . import signals  # noqa: F401
