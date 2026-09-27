"""Each camping is sold with its own website and panel on its own address."""

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings.models import BookingRequest
from campings.models import Camping, unique_slug
from panel.forms import SettingsForm

from .factories import future, make_accommodation, make_camping, make_user

DOMAIN = "www.camping-propio.test"


@override_settings(PLATFORM_HOSTS=["testserver"])
class OwnDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_user()
        self.camping = make_camping("Camping Propio", owner=self.owner, custom_domain=DOMAIN)

    def verify(self):
        Camping.objects.filter(pk=self.camping.pk).update(domain_verified_at=timezone.now())
        cache.clear()
        self.camping.refresh_from_db()

    def test_first_secure_visit_verifies_the_domain(self):
        self.assertTrue(self.camping.domain_pending)
        self.client.get("/es/", HTTP_HOST=DOMAIN)  # plain http does not count
        self.camping.refresh_from_db()
        self.assertIsNone(self.camping.domain_verified_at)
        self.client.get("/es/", HTTP_HOST=DOMAIN, secure=True)
        self.camping.refresh_from_db()
        self.assertIsNotNone(self.camping.domain_verified_at)
        self.assertEqual(self.camping.site_url, f"https://{DOMAIN}")

    def test_changing_the_domain_needs_a_new_verification(self):
        self.verify()
        stale = Camping.objects.get(pk=self.camping.pk)
        stale.domain_verified_at = None  # e.g. loaded before the verification
        stale.save()
        self.camping.refresh_from_db()
        self.assertIsNotNone(self.camping.domain_verified_at)
        self.camping.custom_domain = "www.otro-dominio.test"
        self.camping.save()
        self.assertIsNone(self.camping.domain_verified_at)

    def test_platform_address_redirects_once_the_domain_works(self):
        platform_path = f"/en/camping/{self.camping.slug}/"
        self.assertEqual(self.client.get(platform_path).status_code, 200)  # domain not verified yet
        self.verify()
        response = self.client.get(platform_path + "?utm_source=x")
        self.assertRedirects(response, f"https://{DOMAIN}/en/?utm_source=x", 301, fetch_redirect_response=False)
        response = self.client.get(f"/de/camping/{self.camping.slug}/book/")
        self.assertRedirects(response, f"https://{DOMAIN}/de/book/", 301, fetch_redirect_response=False)
        response = self.client.get(f"/es/camping/{self.camping.slug}/privacy/")
        self.assertRedirects(response, f"https://{DOMAIN}/es/privacy/", 301, fetch_redirect_response=False)
        # The quote endpoint keeps working where it is called from.
        response = self.client.get(f"/en/camping/{self.camping.slug}/quote/")
        self.assertEqual(response.status_code, 200)

    def test_unpublished_campings_are_previewed_on_the_platform(self):
        self.verify()
        self.camping.is_published = False
        self.camping.save()
        self.client.force_login(self.owner)
        response = self.client.get(f"/es/camping/{self.camping.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "preview-banner")

    def test_platform_sitemap_leaves_out_campings_with_their_own_domain(self):
        other = make_camping("Sin dominio")
        self.verify()
        response = self.client.get("/sitemap.xml")
        self.assertContains(response, f"/camping/{other.slug}/")
        self.assertNotContains(response, self.camping.slug)
        response = self.client.get("/sitemap.xml", HTTP_HOST=DOMAIN)
        self.assertContains(response, f"http://{DOMAIN}/es/")

    def test_panel_links_point_to_the_own_domain(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/en/panel/c/{self.camping.slug}/")
        self.assertContains(response, f'href="/en/camping/{self.camping.slug}/"')
        self.assertContains(response, "will be used as soon as its DNS points to us")
        self.verify()
        response = self.client.get(f"/en/panel/c/{self.camping.slug}/")
        self.assertContains(response, f'href="https://{DOMAIN}/en/"')
        self.assertContains(response, f'value="https://{DOMAIN}/"')

    def test_new_booking_email_links_to_the_panel_on_the_own_domain(self):
        self.verify()
        acc = make_accommodation(self.camping)
        self.camping.email = "info@camping-propio.test"
        self.camping.save()
        response = self.client.post(
            "/en/book/",
            {
                "accommodation": acc.pk,
                "arrival": future(10).isoformat(),
                "departure": future(12).isoformat(),
                "adults": 2,
                "name": "Guest",
                "email": "guest@example.com",
                "accept_privacy": "on",
            },
            HTTP_HOST=DOMAIN,
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        booking = BookingRequest.objects.get()
        to_camping, to_guest = mail.outbox
        self.assertIn(f"https://{DOMAIN}/es/panel/c/{self.camping.slug}/bookings/{booking.pk}/", to_camping.body)
        # Guests get the e-mail in the camping's name, replies go to the camping.
        self.assertTrue(to_guest.from_email.startswith("Camping Propio <"))
        self.assertEqual(to_guest.reply_to, ["info@camping-propio.test"])


@override_settings(PLATFORM_HOSTS=["testserver"])
class OwnPanelTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_user()
        self.camping = make_camping("Camping Panel", owner=self.owner, custom_domain=DOMAIN)
        self.other = make_camping("Camping Ajeno", owner=make_user("other@example.com"))

    def get(self, path, **extra):
        return self.client.get(path, HTTP_HOST=DOMAIN, **extra)

    def test_login_on_the_own_domain_leads_to_its_dashboard(self):
        response = self.client.post(
            "/es/panel/login/", {"username": "owner@example.com", "password": "s3cret-pass!"}, HTTP_HOST=DOMAIN
        )
        self.assertRedirects(response, "/es/panel/", fetch_redirect_response=False)
        response = self.get("/es/panel/")
        self.assertRedirects(response, f"/es/panel/c/{self.camping.slug}/", fetch_redirect_response=False)
        response = self.get(f"/es/panel/c/{self.camping.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c.pk for c in response.context["my_campings"]], [self.camping.pk])
        self.assertContains(response, 'href="/es/"')  # "View page" stays on the domain

    def test_only_this_camping_can_be_managed_on_its_domain(self):
        admin = make_user("admin@example.com", is_superuser=True, is_staff=True)
        self.client.force_login(admin)
        self.assertEqual(self.get(f"/es/panel/c/{self.other.slug}/").status_code, 404)
        self.assertEqual(self.get("/es/panel/platform/").status_code, 404)
        self.assertRedirects(self.get("/es/panel/"), f"/es/panel/c/{self.camping.slug}/", fetch_redirect_response=False)
        # On the platform the super-admin still reaches everything.
        self.assertEqual(self.client.get(f"/es/panel/c/{self.other.slug}/").status_code, 200)

    def test_members_of_other_campings_cannot_manage_it(self):
        self.client.force_login(self.other.memberships.get().user)
        response = self.get("/en/panel/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot manage Camping Panel")
        self.assertEqual(self.get(f"/es/panel/c/{self.camping.slug}/").status_code, 404)

    def test_logout_goes_back_to_the_website(self):
        self.client.force_login(self.owner)
        response = self.client.post("/es/panel/logout/", HTTP_HOST=DOMAIN)
        self.assertRedirects(response, "/es/", fetch_redirect_response=False)
        self.client.force_login(self.owner)
        response = self.client.post("/es/panel/logout/")
        self.assertRedirects(response, "/es/panel/login/", fetch_redirect_response=False)

    def test_password_reset_email_uses_the_camping(self):
        response = self.client.post("/es/panel/password/reset/", {"email": "owner@example.com"}, HTTP_HOST=DOMAIN)
        self.assertEqual(response.status_code, 302)
        message = mail.outbox[0]
        self.assertIn("Camping Panel", message.subject)
        self.assertIn(f"http://{DOMAIN}/es/panel/password/reset/", message.body)
        self.assertTrue(message.from_email.startswith("Camping Panel <"))

    def test_team_invitation_links_to_the_own_domain(self):
        Camping.objects.filter(pk=self.camping.pk).update(domain_verified_at=timezone.now())
        self.client.force_login(self.owner)
        response = self.client.post(
            f"/es/panel/c/{self.camping.slug}/team/", {"email": "new@example.com", "role": "staff"}, HTTP_HOST=DOMAIN
        )
        self.assertIn(f"http://{DOMAIN}/es/panel/password/reset/", response.context["invite_link"])


@override_settings(PLATFORM_HOSTS=["testserver"], CAMPING_DOMAIN_SUFFIX="campings.test")
class SubdomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_user()
        self.camping = make_camping("Los Pinos", owner=self.owner)
        self.host = f"{self.camping.slug}.campings.test"

    def test_every_camping_gets_a_subdomain(self):
        self.assertEqual(self.camping.site_url, f"https://{self.host}")
        response = self.client.get("/es/", HTTP_HOST=self.host)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Los Pinos")
        self.assertEqual(self.client.get("/es/panel/login/", HTTP_HOST=self.host).status_code, 200)

    def test_unknown_subdomains_are_rejected(self):
        self.assertEqual(self.client.get("/es/", HTTP_HOST="nadie.campings.test").status_code, 400)
        self.assertEqual(self.client.get("/es/", HTTP_HOST=f"a.{self.host}").status_code, 400)

    def test_platform_address_redirects_to_the_subdomain(self):
        response = self.client.get(f"/fr/camping/{self.camping.slug}/")
        self.assertRedirects(response, f"https://{self.host}/fr/", 301, fetch_redirect_response=False)

    def test_subdomain_redirects_to_the_own_domain_once_it_works(self):
        self.camping.custom_domain = DOMAIN
        self.camping.save()
        self.assertEqual(self.client.get("/es/", HTTP_HOST=self.host).status_code, 200)  # still pending
        Camping.objects.filter(pk=self.camping.pk).update(domain_verified_at=timezone.now())
        cache.clear()
        response = self.client.get("/es/book/?adults=2", HTTP_HOST=self.host, secure=True)
        self.assertRedirects(response, f"https://{DOMAIN}/es/book/?adults=2", 301, fetch_redirect_response=False)

    def test_changing_the_slug_moves_the_subdomain(self):
        self.client.get("/es/", HTTP_HOST=self.host)  # cache the host
        self.camping.slug = "nuevo-nombre"
        self.camping.save()
        self.assertEqual(self.client.get("/es/", HTTP_HOST=self.host).status_code, 400)
        self.assertEqual(self.client.get("/es/", HTTP_HOST="nuevo-nombre.campings.test").status_code, 200)

    def test_settings_show_the_subdomain(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/es/panel/c/{self.camping.slug}/settings/", HTTP_HOST=self.host)
        self.assertContains(response, ".campings.test</span>")


class WhiteLabelTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Marca Blanca", owner=self.owner)
        self.url = f"/en/camping/{self.camping.slug}/"

    def test_credit_can_be_hidden(self):
        self.assertContains(self.client.get(self.url), "Powered by")
        self.camping.show_platform_credit = False
        self.camping.save()
        self.assertNotContains(self.client.get(self.url), "Powered by")

    def test_only_platform_admins_manage_domain_and_credit(self):
        self.assertNotIn("show_platform_credit", SettingsForm(instance=self.camping).fields)
        self.assertNotIn("custom_domain", SettingsForm(instance=self.camping).fields)
        form = SettingsForm(instance=self.camping, allow_domain=True)
        self.assertIn("show_platform_credit", form.fields)

    def test_platform_admin_sets_the_domain_as_pasted(self):
        admin = make_user("admin@example.com", is_superuser=True, is_staff=True)
        self.client.force_login(admin)
        response = self.client.post(
            f"/es/panel/c/{self.camping.slug}/settings/",
            {
                "slug": self.camping.slug,
                "default_language": "es",
                "languages": ["es"],
                "currency": "EUR",
                "accepts_booking_requests": "on",
                "custom_domain": "https://WWW.Marca-Blanca.test/",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.custom_domain, "www.marca-blanca.test")
        self.assertFalse(self.camping.show_platform_credit)


class SlugTests(TestCase):
    def test_slugs_are_valid_subdomains(self):
        self.assertEqual(unique_slug("Camping_El Sol", Camping), "camping-el-sol")
        self.assertEqual(unique_slug("www", Camping), "www-camping")
        self.assertLessEqual(len(unique_slug("x" * 200, Camping)), 63)

    def test_settings_reject_invalid_slugs(self):
        camping = make_camping("Valido")
        data = {"default_language": "es", "languages": ["es"], "currency": "EUR"}
        for slug in ("con_guion_bajo", "-empieza", "www"):
            form = SettingsForm({**data, "slug": slug}, instance=camping)
            self.assertIn("slug", form.errors, slug)
