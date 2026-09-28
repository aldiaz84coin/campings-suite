"""Legal notice, privacy and cookie pages, statistics consent and Google codes."""

from django.core.cache import cache
from django.test import TestCase, override_settings

from campings.models import Membership

from .factories import make_camping, make_user
from .test_panel import panel_url


class LegalPagesTests(TestCase):
    def setUp(self):
        self.camping = make_camping(
            "Camping Legal",
            email="info@legal.test",
            address="Carretera de la Costa, km 3",
            postal_code="17250",
            city="Platja d'Aro",
            legal_name="Legal Turisme, S.L.",
            tax_id="B17123456",
            registry_info="Registro Mercantil de Girona, tomo 1",
            tourism_registration="KG-000123",
        )
        self.base = f"/en/camping/{self.camping.slug}"

    def test_legal_notice_lists_the_owner(self):
        response = self.client.get(f"{self.base}/legal/")
        self.assertContains(response, "Legal Turisme, S.L.")
        self.assertContains(response, "B17123456")
        self.assertContains(response, "Registro Mercantil de Girona")
        self.assertContains(response, "KG-000123")
        self.assertContains(response, "Carretera de la Costa, km 3, 17250 Platja d&#x27;Aro")

    def test_owner_defaults_to_the_camping(self):
        self.camping.legal_name = ""
        self.camping.legal_address = "Calle Mayor 1, Girona"
        self.camping.save()
        response = self.client.get(f"{self.base}/legal/")
        self.assertContains(response, "<strong>Owner:</strong> Camping Legal", html=False)
        self.assertContains(response, "Calle Mayor 1, Girona")

    def test_privacy_policy(self):
        self.camping.privacy_extra = {"es": "Texto adicional", "en": "Extra privacy text"}
        self.camping.save()
        response = self.client.get(f"{self.base}/privacy/")
        self.assertContains(response, "Legal Turisme, S.L.")
        self.assertContains(response, "article 6.1.b GDPR")
        self.assertContains(response, "www.aepd.es")
        self.assertContains(response, f"{self.base}/cookies/")
        self.assertContains(response, "Extra privacy text")

    def test_cookie_policy_lists_statistics_only_when_used(self):
        response = self.client.get(f"{self.base}/cookies/")
        self.assertContains(response, "csrftoken")
        self.assertNotContains(response, "_ga")
        self.camping.ga_measurement_id = "G-AB12CD34EF"
        self.camping.save()
        response = self.client.get(f"{self.base}/cookies/")
        self.assertContains(response, "_ga")
        self.assertContains(response, "data-consent-reset")

    def test_footer_links_and_registration_number(self):
        response = self.client.get(f"{self.base}/")
        for path in ("legal/", "privacy/", "cookies/"):
            self.assertContains(response, f'href="{self.base}/{path}"')
        self.assertContains(response, "Tourism reg. no. KG-000123")

    def test_consent_banner_and_search_console(self):
        response = self.client.get(f"{self.base}/")
        self.assertNotContains(response, "data-consent ")
        self.assertNotContains(response, "google-site-verification")
        self.camping.ga_measurement_id = "G-AB12CD34EF"
        self.camping.search_console_verification = "AbCdEf123456_ghIJkl"
        self.camping.save()
        response = self.client.get(f"{self.base}/")
        self.assertContains(response, 'data-ga="G-AB12CD34EF"')
        self.assertContains(response, '<meta name="google-site-verification" content="AbCdEf123456_ghIJkl">')
        # Analytics is never written into the page: the script loads it after consent.
        self.assertNotContains(response, "googletagmanager")

    @override_settings(PLATFORM_HOSTS=["testserver"])
    def test_pages_on_the_camping_domain(self):
        cache.clear()
        self.camping.custom_domain = "www.legal.test"
        self.camping.save()
        for path in ("/es/legal/", "/es/privacy/", "/es/cookies/"):
            self.assertEqual(self.client.get(path, HTTP_HOST="www.legal.test").status_code, 200, path)


class LegalPanelTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Camping Panel Legal", owner=self.owner)
        self.client.force_login(self.owner)

    def test_owner_saves_legal_details(self):
        url = panel_url("legal", self.camping)
        self.assertContains(self.client.get(url), 'placeholder="Camping Panel Legal"')
        response = self.client.post(
            url,
            {
                "legal_name": "Panel Legal, S.L.",
                "tax_id": "B12345678",
                "legal_address": "",
                "registry_info": "",
                "tourism_registration": "KG-1",
                "legal_notice_extra_es": "Más información",
            },
        )
        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.owner_name, "Panel Legal, S.L.")
        self.assertEqual(self.camping.legal_notice_extra, {"es": "Más información"})
        dashboard = self.client.get(panel_url("dashboard", self.camping))
        item = next(item for item in dashboard.context["checklist"] if item["url_name"] == "panel:legal")
        self.assertTrue(item["done"])

    def test_staff_cannot_edit_legal_details(self):
        staff = make_user("staff@example.com")
        Membership.objects.create(user=staff, camping=self.camping, role=Membership.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(panel_url("legal", self.camping)).status_code, 403)

    def settings_data(self, **extra):
        data = {
            "slug": self.camping.slug,
            "default_language": "es",
            "languages": ["es"],
            "currency": "EUR",
            "accepts_booking_requests": "on",
            "ga_measurement_id": "",
            "search_console_verification": "",
        }
        data.update(extra)
        return data

    def test_google_codes_in_settings(self):
        url = panel_url("settings", self.camping)
        response = self.client.post(
            url,
            self.settings_data(
                ga_measurement_id=" g-ab12cd34ef ",
                search_console_verification='<meta name="google-site-verification" content="AbCdEf123456_ghIJkl" />',
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.ga_measurement_id, "G-AB12CD34EF")
        self.assertEqual(self.camping.search_console_verification, "AbCdEf123456_ghIJkl")
        response = self.client.post(url, self.settings_data(ga_measurement_id="UA-12345-1"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("ga_measurement_id", response.context["form"].errors)
