import mimetypes
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.utils.encoding import filepath_to_uri


@deconstructible
class DatabaseStorage(Storage):
    """Stores uploaded files as rows of :class:`core.models.StoredFile`.

    Handy on Fly.io when no bucket or volume is configured: photos survive
    deploys because they live in PostgreSQL. Files are served by
    :func:`core.views.media` with long-lived cache headers.
    """

    @staticmethod
    def _model():
        from core.models import StoredFile

        return StoredFile

    def _open(self, name, mode="rb"):
        try:
            obj = self._model().objects.get(name=name)
        except self._model().DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(bytes(obj.content), name=name)

    def _save(self, name, content):
        if hasattr(content, "seek"):
            content.seek(0)
        data = b"".join(content.chunks()) if hasattr(content, "chunks") else content.read()
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self._model().objects.update_or_create(
            name=name,
            defaults={"content": data, "size": len(data), "content_type": content_type},
        )
        return name

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def size(self, name):
        obj = self._model().objects.filter(name=name).only("size").first()
        if obj is None:
            raise FileNotFoundError(name)
        return obj.size

    def url(self, name):
        return urljoin(settings.MEDIA_URL, filepath_to_uri(name))

    def get_created_time(self, name):
        obj = self._model().objects.filter(name=name).only("created_at").first()
        if obj is None:
            raise FileNotFoundError(name)
        return obj.created_at

    get_modified_time = get_created_time
