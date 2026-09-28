"""The demo camping used to show the product to new campings."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from campings.models import Camping, Membership


class SeedDemoTests(TestCase):
    def test_seed_demo_creates_a_complete_camping(self):
        out = StringIO()
        call_command("seed_demo", "--no-photos", "--owner-password", "demo12345", stdout=out)
        self.assertIn("demo@example.com / demo12345", out.getvalue())
        camping = Camping.objects.get(slug="los-pinos-demo")
        self.assertTrue(Membership.objects.filter(camping=camping, user__email="demo@example.com").exists())
        self.assertTrue(camping.seasons.exists())
        base = f"/es/camping/{camping.slug}"
        for path in ("/", "/privacy/", "/cookies/"):
            self.assertEqual(self.client.get(base + path).status_code, 200, path)
        self.assertContains(self.client.get(f"{base}/legal/"), "B00000000")

        # Running it again recreates the camping instead of failing.
        call_command("seed_demo", "--no-photos", stdout=StringIO())
        self.assertEqual(Camping.objects.filter(slug="los-pinos-demo").count(), 1)
