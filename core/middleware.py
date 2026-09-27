import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponsePermanentRedirect
from django.http.request import split_domain_port, validate_host

logger = logging.getLogger(__name__)

CUSTOM_DOMAIN_URLCONF = "config.urls_custom_domain"
_CACHE_PREFIX = "custom-domain:"
_CACHE_TTL = 60


def custom_domain_camping_id(domain):
    """Id of the public camping served on ``domain`` (cached), or ``None``."""
    key = _CACHE_PREFIX + domain
    camping_id = cache.get(key)
    if camping_id is None:
        from campings.models import Camping

        camping_id = (
            Camping.objects.filter(custom_domain=domain, is_published=True, is_approved=True)
            .values_list("id", flat=True)
            .first()
        ) or 0
        cache.set(key, camping_id, _CACHE_TTL)
    return camping_id or None


def forget_custom_domain(domain):
    if domain:
        cache.delete(_CACHE_PREFIX + domain)


def _platform_hosts():
    hosts = settings.PLATFORM_HOSTS
    if settings.DEBUG and not hosts:
        hosts = [".localhost", "127.0.0.1", "[::1]"]
    return hosts


class HostRoutingMiddleware:
    """Validates the Host header and routes camping custom domains.

    * ``/healthz`` always answers (Fly.io health checks use internal hosts).
    * Platform hosts (``ALLOWED_HOSTS`` env var) get the normal URLconf.
    * A camping's own domain gets ``config.urls_custom_domain``.
    * Anything else is rejected with 400, like Django's ALLOWED_HOSTS check.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.domain_camping_id = None
        if request.path == "/healthz":
            return HttpResponse("ok", content_type="text/plain")

        raw_host = request.META.get("HTTP_HOST") or request.META.get("SERVER_NAME", "")
        domain, _port = split_domain_port(raw_host)
        if not domain:
            return HttpResponseBadRequest("Invalid Host header")
        if validate_host(domain, _platform_hosts()):
            return self.get_response(request)

        camping_id = custom_domain_camping_id(domain)
        if camping_id:
            request.urlconf = CUSTOM_DOMAIN_URLCONF
            request.domain_camping_id = camping_id
            return self.get_response(request)

        # www.example.com <-> example.com
        alternative = domain[4:] if domain.startswith("www.") else f"www.{domain}"
        if custom_domain_camping_id(alternative):
            scheme = "https" if request.META.get("HTTP_X_FORWARDED_PROTO") == "https" or request.is_secure() else "http"
            return HttpResponsePermanentRedirect(f"{scheme}://{alternative}{request.get_full_path()}")

        logger.warning("Rejected request for unknown host %r", domain)
        return HttpResponseBadRequest("Unknown host")
