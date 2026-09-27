from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.views.decorators.http import require_GET
from django.views.static import serve

CACHE_FOREVER = "public, max-age=31536000, immutable"


@require_GET
def healthz(request):
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def media(request, path):
    """Serves uploads when they are stored on disk or in the database.

    File names are random and never reused, so they can be cached forever.
    """
    if settings.MEDIA_STORAGE == "local":
        response = serve(request, path, document_root=settings.MEDIA_ROOT)
        response["Cache-Control"] = CACHE_FOREVER
        return response

    from core.models import StoredFile

    stored = StoredFile.objects.filter(name=path).only("id", "size", "content_type").first()
    if stored is None:
        raise Http404("File not found")
    etag = f'"{stored.pk}-{stored.size}"'
    if request.headers.get("If-None-Match") == etag:
        response = HttpResponseNotModified()
    else:
        content = StoredFile.objects.filter(pk=stored.pk).values_list("content", flat=True).get()
        response = HttpResponse(bytes(content), content_type=stored.content_type)
    response["ETag"] = etag
    response["Cache-Control"] = CACHE_FOREVER
    return response
