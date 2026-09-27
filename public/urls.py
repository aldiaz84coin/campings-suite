from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("privacy/", views.privacy, name="privacy"),
    path("camping/<slug:slug>/", views.camping_detail, name="camping_detail"),
    path("camping/<slug:slug>/book/", views.booking, name="booking"),
    path("camping/<slug:slug>/book/done/<uuid:token>/", views.booking_done, name="booking_done"),
    path("camping/<slug:slug>/quote/", views.quote, name="quote"),
    path("camping/<slug:slug>/privacy/", views.privacy, name="camping_privacy"),
]
