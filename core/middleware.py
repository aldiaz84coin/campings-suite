import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponsePermanentRedirect
from django.http.request import split_domain_port, validate_host
from django.utils import timezone

logger = logging.getLogger(__name__)

CAMPING_URLCONF = "config.urls_custom_domain"
_CACHE_PREFIX = "camping-host:"
_CACHE_TTL = 60


def subdomain_suffix():
    """Domain part of ``CAMPING_DOMAIN_SUFFIX`` (without port), or ""."""
    return split_domain_port(settings.CAMPING_DOMAIN_SUFFIX)[0] if settings.CAMPING_DOMAIN_SUFFIX else ""


def _lookup_host(domain):
    from campings.models import Camping

    suffix = subdomain_suffix()
    if suffix and domain.endswith(f".{suffix}"):
        label = domain[: -len(suffix) - 1]
        if "." in label:
            return None
        row = Camping.objects.filter(slug=label).values("id", "custom_domain", "domain_verified_at").first()
        if row is None:
            return None
        # Once its own domain works, the subdomain only redirects to it.
        redirect = row["custom_domain"] if row["domain_verified_at"] else None
        return {"id": row["id"], "own_domain": False, "verified": True, "redirect": redirect}

    row = Camping.objects.filter(custom_domain=domain).values("id", "domain_verified_at").first()
    if row is None:
        return None
    return {"id": row["id"], "own_domain": True, "verified": bool(row["domain_verified_at"]), "redirect": None}


def camping_for_host(domain):
    """How ``domain`` maps to a camping (cached dict), or ``None``."""
    key = _CACHE_PREFIX + domain
    match = cache.get(key)
    if match is None:
        match = _lookup_host(domain) or {}
        cache.set(key, match, _CACHE_TTL)
    return match or None


def forget_hosts(*domains):
    cache.delete_many([_CACHE_PREFIX + domain for domain in domains if domain])


def camping_hosts(slug=None, custom_domain=None):
    """Hosts that may serve a camping (to clear the cache when it changes)."""
    hosts = [custom_domain]
    suffix = subdomain_suffix()
    if slug and suffix:
        hosts.append(f"{slug}.{suffix}")
    return [host for host in hosts if host]


def _platform_hosts():
    hosts = settings.PLATFORM_HOSTS
    if settings.DEBUG and not hosts:
        hosts = [".localhost", "127.0.0.1", "[::1]"]
    return hosts


def _scheme(request):
    return "https" if request.is_secure() or request.META.get("HTTP_X_FORWARDED_PROTO") == "https" else "http"


class HostRoutingMiddleware:
    """Validates the Host header and serves every camping on its own address.

    * ``/healthz`` always answers (Fly.io health checks use internal hosts).
    * Platform hosts (``ALLOWED_HOSTS`` env var) get the normal URLconf: panel
      for every camping, super-admin and sites without an address of their own.
    * A camping's own domain, or its ``<slug>.<CAMPING_DOMAIN_SUFFIX>``
      subdomain, gets ``config.urls_custom_domain``: its website at the root
      and its own panel under ``/<lang>/panel/``.
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

        match = camping_for_host(domain)
        if match:
            if match["redirect"]:
                return HttpResponsePermanentRedirect(
                    f"{_scheme(request)}://{match['redirect']}{request.get_full_path()}"
                )
            if match["own_domain"] and not match["verified"] and (request.is_secure() or settings.DEBUG):
                self._mark_verified(match["id"], domain)
            request.urlconf = CAMPING_URLCONF
            request.domain_camping_id = match["id"]
            return self.get_response(request)

        # www.example.com <-> example.com
        alternative = domain[4:] if domain.startswith("www.") else f"www.{domain}"
        alternative_match = camping_for_host(alternative)
        if alternative_match and alternative_match["own_domain"]:
            return HttpResponsePermanentRedirect(f"{_scheme(request)}://{alternative}{request.get_full_path()}")

        logger.warning("Rejected request for unknown host %r", domain)
        return HttpResponseBadRequest("Unknown host")

    @staticmethod
    def _mark_verified(camping_id, domain):
        from campings.models import Camping

        slug = Camping.objects.filter(pk=camping_id).values_list("slug", flat=True).first()
        updated = Camping.objects.filter(pk=camping_id, domain_verified_at__isnull=True).update(
            domain_verified_at=timezone.now()
        )
        if updated:
            logger.info("Own domain %s is now receiving visits", domain)
        forget_hosts(domain, *camping_hosts(slug=slug))
