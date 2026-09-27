from django.conf import settings


def platform(request):
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "PLATFORM_URL": settings.PLATFORM_URL,
        "SIGNUP_ENABLED": settings.SIGNUP_ENABLED,
        "on_custom_domain": bool(getattr(request, "domain_camping_id", None)),
    }
