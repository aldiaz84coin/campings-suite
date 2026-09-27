import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Creates the platform superuser from DJANGO_SUPERUSER_EMAIL and "
        "DJANGO_SUPERUSER_PASSWORD if it does not exist yet. Safe to run on every deploy."
    )

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not email or not password:
            self.stdout.write("DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD not set: nothing to do.")
            return
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(f"Superuser {email} already exists.")
            return
        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superuser {email} created."))
