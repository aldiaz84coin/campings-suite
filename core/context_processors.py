from django.conf import settings
from django.utils.functional import SimpleLazyObject


def _site_camping(camping_id):
    from campings.models import Camping

    return Camping.objects.filter(pk=camping_id).first()


def platform(request):
    camping_id = getattr(request, "domain_camping_id", None)
    site_camping = SimpleLazyObject(lambda: _site_camping(camping_id)) if camping_id else None
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "PLATFORM_URL": settings.PLATFORM_URL,
        "PLATFORM_CREDIT_URL": settings.PLATFORM_CREDIT_URL,
        "SIGNUP_ENABLED": settings.SIGNUP_ENABLED and not camping_id,
        "on_custom_domain": bool(camping_id),
        # The camping whose own address serves this request (lazy, one query).
        "site_camping": site_camping,
        "SITE_NAME": SimpleLazyObject(lambda: site_camping.name) if camping_id else settings.PLATFORM_NAME,
    }
