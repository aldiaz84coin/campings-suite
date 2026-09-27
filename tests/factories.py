from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from campings.models import AccommodationType, Camping, Membership, Season, Service


def make_user(email="owner@example.com", password="s3cret-pass!", **extra):
    return get_user_model().objects.create_user(email=email, password=password, **extra)


def make_camping(name="Camping Test", owner=None, role=Membership.Role.OWNER, **extra):
    defaults = {
        "is_published": True,
        "is_approved": True,
        "default_language": "es",
        "languages": ["es", "en"],
        "description": {"es": "Descripción", "en": "Description"},
        "tagline": {"es": "Lema", "en": "Tagline"},
    }
    defaults.update(extra)
    camping = Camping.objects.create(name=name, **defaults)
    if owner is not None:
        Membership.objects.create(user=owner, camping=camping, role=role)
    return camping


def make_accommodation(camping, **extra):
    defaults = {
        "kind": "bungalow",
        "name": {"es": "Bungalow", "en": "Bungalow EN"},
        "max_guests": 4,
        "units": 1,
        "base_price": Decimal("50"),
    }
    defaults.update(extra)
    return AccommodationType.objects.create(camping=camping, **defaults)


def make_season(camping, start, end, **extra):
    defaults = {"name": {"es": "Alta", "en": "High"}}
    defaults.update(extra)
    return Season.objects.create(camping=camping, start_date=start, end_date=end, **defaults)


def make_service(camping, **extra):
    defaults = {"name": {"es": "Adulto", "en": "Adult"}, "price": Decimal("5"), "unit": "adult_night", "mode": "mandatory"}
    defaults.update(extra)
    return Service.objects.create(camping=camping, **defaults)


def future(days):
    return timezone.localdate() + timedelta(days=days)


def image_file(name="photo.jpg", size=(1200, 800), color=(40, 120, 80), fmt="JPEG"):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, fmt)
    content_type = "image/png" if fmt == "PNG" else "image/jpeg"
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)
