from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from core import views as core_views
from public import views as public_views

admin.site.site_header = settings.PLATFORM_NAME
admin.site.site_title = settings.PLATFORM_NAME
admin.site.index_title = _("Platform administration")

urlpatterns = [
    path("healthz", core_views.healthz, name="healthz"),
    path("robots.txt", public_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", public_views.sitemap_xml, name="sitemap"),
    path("superadmin/", admin.site.urls),
]

if settings.MEDIA_STORAGE in ("local", "db"):
    urlpatterns.append(path("media/<path:path>", core_views.media, name="media"))

urlpatterns += i18n_patterns(
    path("", include("public.urls")),
    path("panel/", include("panel.urls")),
    prefix_default_language=True,
)
