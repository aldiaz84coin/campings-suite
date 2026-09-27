from django.db import models
from django.utils.translation import gettext_lazy as _


class StoredFile(models.Model):
    """Binary file kept in the database (``MEDIA_STORAGE=db``)."""

    name = models.CharField(_("name"), max_length=255, unique=True)
    content = models.BinaryField(_("content"))
    content_type = models.CharField(_("content type"), max_length=100)
    size = models.PositiveIntegerField(_("size"), default=0)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        verbose_name = _("stored file")
        verbose_name_plural = _("stored files")

    def __str__(self):
        return self.name
