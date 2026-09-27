"""URLconf used when a request arrives through a camping's own domain.

``core.middleware.HostRoutingMiddleware`` switches to it, so
``https://www.my-camping.com/es/`` shows that camping's public site directly.
"""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path

from core import views as core_views
from public import views as public_views

urlpatterns = [
    path("healthz", core_views.healthz, name="healthz"),
    path("robots.txt", public_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", public_views.sitemap_xml, name="sitemap"),
]

if settings.MEDIA_STORAGE in ("local", "db"):
    urlpatterns.append(path("media/<path:path>", core_views.media, name="media"))

urlpatterns += i18n_patterns(
    path("", include("public.urls_domain")),
    prefix_default_language=True,
)
