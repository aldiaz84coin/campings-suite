from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PanelConfig(AppConfig):
    name = "panel"
    verbose_name = _("Camping panel")
