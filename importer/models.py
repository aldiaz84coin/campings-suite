from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from campings.models import Camping


class SiteImport(models.Model):
    """What was read from a camping's current website, waiting for review."""

    class Status(models.TextChoices):
        READY = "ready", _("Ready to review")
        APPLIED = "applied", _("Imported")

    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="site_imports")
    url = models.URLField(_("website"), max_length=500)
    status = models.CharField(_("status"), max_length=10, choices=Status.choices, default=Status.READY)
    data = models.JSONField(default=dict, blank=True)
    # Photos chosen in the review, downloaded a few at a time.
    photo_queue = models.JSONField(default=list, blank=True)
    photos_done = models.PositiveIntegerField(default=0)
    photos_failed = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("website import")
        verbose_name_plural = _("website imports")

    def __str__(self):
        return f"{self.camping} · {self.url}"

    @property
    def photos_total(self):
        return self.photos_done + self.photos_failed + len(self.photo_queue or [])
