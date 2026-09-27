"""Public URLs on a camping's own domain: same names, no slug."""

from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.camping_detail, name="camping_detail"),
    path("", views.camping_detail, name="home"),
    path("privacy/", views.privacy, name="camping_privacy"),
    path("privacy/", views.privacy, name="privacy"),
    path("book/", views.booking, name="booking"),
    path("book/done/<uuid:token>/", views.booking_done, name="booking_done"),
    path("quote/", views.quote, name="quote"),
]
