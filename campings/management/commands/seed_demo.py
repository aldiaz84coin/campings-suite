import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from campings.demo import create_demo_camping
from campings.models import Membership


class Command(BaseCommand):
    help = "Creates a complete demo camping (photos, prices, seasons, policies) and its owner account."

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="los-pinos-demo")
        parser.add_argument("--owner-email", default="demo@example.com")
        parser.add_argument("--owner-password", default="", help="Random if omitted (printed at the end).")
        parser.add_argument("--no-photos", action="store_true", help="Skip generating photos.")

    @transaction.atomic
    def handle(self, *args, **options):
        camping = create_demo_camping(slug=options["slug"], with_photos=not options["no_photos"])
        User = get_user_model()
        email = options["owner_email"].lower()
        password = options["owner_password"] or secrets.token_urlsafe(9)
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=password, first_name="Demo")
            created = True
        else:
            created = False
            if options["owner_password"]:
                user.set_password(password)
                user.save()
        Membership.objects.get_or_create(user=user, camping=camping, defaults={"role": Membership.Role.OWNER})
        self.stdout.write(self.style.SUCCESS(f"Demo camping ready: /es/camping/{camping.slug}/"))
        if created or options["owner_password"]:
            self.stdout.write(f"Owner login: {email} / {password}")
        else:
            self.stdout.write(f"Owner login: {email} (existing password)")
