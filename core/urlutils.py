from django.conf import settings
from django.urls import reverse

from core.middleware import CAMPING_URLCONF


def request_camping_id(request):
    """Id of the camping whose own host serves ``request``, or ``None``."""
    return getattr(request, "domain_camping_id", None) if request is not None else None


def camping_reverse(request, name, camping, **kwargs):
    """Reverse a public camping URL for the platform or a camping's own host.

    On a camping's own domain the URLs carry no slug (the domain identifies
    the camping), so the same template can serve both cases.
    """
    if request_camping_id(request):
        return reverse(name, kwargs=kwargs or None)
    return reverse(name, kwargs={"slug": camping.slug, **kwargs})


def platform_url(request, path):
    """Absolute URL on the platform host (not on a camping's own domain)."""
    if settings.PLATFORM_URL:
        return f"{settings.PLATFORM_URL}{path}"
    if request is not None and not request_camping_id(request):
        return request.build_absolute_uri(path)
    return path


def camping_site_url(camping, name="public:camping_detail", **kwargs):
    """Absolute URL of a page on the camping's own host, or "" if it has none."""
    if not camping.site_url:
        return ""
    return camping.site_url + reverse(name, urlconf=CAMPING_URLCONF, kwargs=kwargs or None)


def camping_public_url(request, camping, name="public:camping_detail", absolute=False, **kwargs):
    """Where to link a camping's public page from the panel or the platform.

    Relative on the camping's own host; its own website once it is public;
    otherwise the platform address, which also works as a preview for members.
    """
    if request_camping_id(request) == camping.pk:
        path = reverse(name, kwargs=kwargs or None)
    elif camping.is_public and camping.site_url:
        return camping_site_url(camping, name, **kwargs)
    else:
        path = reverse(name, urlconf=settings.ROOT_URLCONF, kwargs={"slug": camping.slug, **kwargs})
        if request_camping_id(request):
            return platform_url(request, path)
    if absolute and request is not None:
        return request.build_absolute_uri(path)
    return path


def camping_panel_url(request, camping, path):
    """Absolute URL of a panel ``path`` for ``camping``, on its own host if it has one.

    Panel paths are the same on the platform and on a camping's own host.
    """
    if request_camping_id(request) == camping.pk:
        return request.build_absolute_uri(path)
    if camping.site_url:
        return f"{camping.site_url}{path}"
    return platform_url(request, path)
