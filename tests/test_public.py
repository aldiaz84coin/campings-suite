from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from bookings.models import BookingRequest
from campings.models import Photo

from .factories import future, make_accommodation, make_camping, make_service, make_user


class DirectoryTests(TestCase):
    def test_root_redirects_to_a_language(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="de")
        self.assertRedirects(response, "/de/", fetch_redirect_response=False)

    def test_only_public_campings_are_listed(self):
        make_camping("Visible")
        make_camping("Draft", is_published=False)
        make_camping("Suspended", is_approved=False)
        response = self.client.get("/es/")
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Draft")
        self.assertNotContains(response, "Suspended")

    def test_search_and_facility_filter(self):
        pool = make_camping("Camping Piscina", city="Tossa")
        make_camping("Camping Montaña", city="Jaca")
        pool.facilities.create(kind="pool")
        self.assertContains(self.client.get("/es/?q=tossa"), "Camping Piscina")
        self.assertNotContains(self.client.get("/es/?q=tossa"), "Camping Montaña")
        response = self.client.get("/es/?facility=pool")
        self.assertContains(response, "Camping Piscina")
        self.assertNotContains(response, "Camping Montaña")

    def test_every_language_renders(self):
        make_camping("Multi")
        for code in ("es", "en", "fr", "de", "nl", "it"):
            response = self.client.get(f"/{code}/")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'lang="{code}"')

    def test_seo_endpoints(self):
        camping = make_camping("Sitemap Camping")
        sitemap = self.client.get("/sitemap.xml")
        self.assertContains(sitemap, f"/es/camping/{camping.slug}/")
        self.assertContains(sitemap, 'hreflang="en"')
        robots = self.client.get("/robots.txt")
        self.assertContains(robots, "Sitemap:")
        self.assertEqual(self.client.get("/healthz").content, b"ok")


class CampingPageTests(TestCase):
    def setUp(self):
        self.camping = make_camping("Camping Los Pinos", languages=["es", "en"])
        self.acc = make_accommodation(self.camping)
        make_service(self.camping)
        self.camping.facilities.create(kind="pool")

    def test_page_shows_content_in_requested_language(self):
        response = self.client.get(f"/en/camping/{self.camping.slug}/")
        self.assertContains(response, "Bungalow EN")
        self.assertContains(response, "Tagline")
        self.assertContains(response, "application/ld+json")
        self.assertContains(response, 'hreflang="es"')
        self.assertNotContains(response, 'name="robots"')

    def test_untranslated_language_falls_back_and_is_noindex(self):
        response = self.client.get(f"/de/camping/{self.camping.slug}/")
        self.assertContains(response, "Lema")  # Spanish fallback (the camping has no German)
        self.assertContains(response, '<meta name="robots" content="noindex">', html=False)

    def test_unpublished_is_hidden_but_members_can_preview(self):
        self.camping.is_published = False
        self.camping.save()
        url = f"/es/camping/{self.camping.slug}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        owner = make_user()
        self.camping.memberships.create(user=owner, role="owner")
        self.client.force_login(owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "preview-banner")

    def test_quote_endpoint(self):
        response = self.client.get(
            f"/en/camping/{self.camping.slug}/quote/",
            {"accommodation": self.acc.pk, "arrival": future(10).isoformat(), "departure": future(12).isoformat(), "adults": 2},
        )
        data = response.json()
        self.assertTrue(data["ok"], data)
        self.assertEqual(data["total"], "120.00")  # 2 x 50 + 2 adults x 2 nights x 5

    def test_quote_endpoint_rejects_bad_input(self):
        response = self.client.get(f"/en/camping/{self.camping.slug}/quote/", {"accommodation": "x"})
        self.assertFalse(response.json()["ok"])


class BookingFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.camping = make_camping("Camping Reservas", email="camping@example.com")
        self.acc = make_accommodation(self.camping)
        self.url = f"/fr/camping/{self.camping.slug}/book/"

    def post(self, **overrides):
        data = {
            "accommodation": self.acc.pk,
            "arrival": future(20).isoformat(),
            "departure": future(23).isoformat(),
            "adults": 2,
            "children": "",
            "name": "Marie",
            "email": "marie@example.com",
            "accept_privacy": "on",
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_booking_request_is_saved_and_notified(self):
        response = self.post()
        booking = BookingRequest.objects.get()
        self.assertRedirects(response, f"/fr/camping/{self.camping.slug}/book/done/{booking.token}/")
        self.assertEqual(booking.language, "fr")
        self.assertEqual(booking.children, 0)
        self.assertEqual(booking.estimated_total, Decimal("150.00"))
        self.assertIn("fr", booking.quote)
        self.assertIn("es", booking.quote)
        self.assertEqual(booking.accommodation_name, "Bungalow")  # camping language
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["camping@example.com"])
        self.assertEqual(mail.outbox[1].to, ["marie@example.com"])
        done = self.client.get(response["Location"])
        self.assertContains(done, booking.reference)

    def test_invalid_stay_is_rejected(self):
        response = self.post(departure=future(20).isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_privacy_consent_is_required(self):
        response = self.post(accept_privacy="")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BookingRequest.objects.exists())

    def test_honeypot_discards_spam(self):
        response = self.post(website="http://spam.example")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BookingRequest.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit(self):
        for _ in range(6):
            self.post()
        self.assertEqual(BookingRequest.objects.count(), 6)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BookingRequest.objects.count(), 6)

    def test_other_campings_accommodation_is_refused(self):
        other = make_accommodation(make_camping("Otro"))
        self.post(accommodation=other.pk)
        self.assertFalse(BookingRequest.objects.exists())

    def test_done_page_needs_the_secret_token(self):
        self.post()
        booking = BookingRequest.objects.get()
        other = make_camping("Otro camping")
        response = self.client.get(f"/fr/camping/{other.slug}/book/done/{booking.token}/")
        self.assertEqual(response.status_code, 404)

    def test_disabled_booking_requests(self):
        self.camping.accepts_booking_requests = False
        self.camping.save()
        self.post()
        self.assertFalse(BookingRequest.objects.exists())


@override_settings(PLATFORM_HOSTS=["testserver"])
class CustomDomainTests(TestCase):
    def setUp(self):
        cache.clear()
        self.camping = make_camping("Camping Dominio", custom_domain="www.camping-dominio.test")
        self.acc = make_accommodation(self.camping)

    def test_custom_domain_serves_the_camping_at_the_root(self):
        response = self.client.get("/es/", HTTP_HOST="www.camping-dominio.test")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camping Dominio")
        self.assertContains(response, 'href="/es/book/"')

    def test_booking_page_and_quote_on_custom_domain(self):
        self.assertEqual(self.client.get("/en/book/", HTTP_HOST="www.camping-dominio.test").status_code, 200)
        response = self.client.get(
            "/en/quote/",
            {"accommodation": self.acc.pk, "arrival": future(5).isoformat(), "departure": future(7).isoformat()},
            HTTP_HOST="www.camping-dominio.test",
        )
        self.assertTrue(response.json()["ok"])

    def test_bare_domain_redirects_to_www(self):
        response = self.client.get("/es/", HTTP_HOST="camping-dominio.test")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "http://www.camping-dominio.test/es/")

    def test_unknown_hosts_are_rejected(self):
        self.assertEqual(self.client.get("/es/", HTTP_HOST="evil.test").status_code, 400)

    def test_panel_is_not_reachable_on_custom_domains(self):
        self.assertEqual(self.client.get("/es/panel/login/", HTTP_HOST="www.camping-dominio.test").status_code, 404)

    def test_unpublished_camping_domain_is_rejected(self):
        self.camping.is_published = False
        self.camping.save()
        self.assertEqual(self.client.get("/es/", HTTP_HOST="www.camping-dominio.test").status_code, 400)

    def test_sitemap_lists_only_that_camping(self):
        make_camping("Otro")
        response = self.client.get("/sitemap.xml", HTTP_HOST="www.camping-dominio.test")
        self.assertContains(response, "http://www.camping-dominio.test/es/")
        self.assertNotContains(response, "/camping/")


class PhotoRenderingTests(TestCase):
    def test_gallery_uses_processed_images(self):
        from core.images import process_photo

        from .factories import image_file

        camping = make_camping("Fotos")
        large, thumb = process_photo(image_file())
        photo = Photo(camping=camping, width=large.width, height=large.height, caption={"es": "Piscina"})
        photo.image.save(large.file.name, large.file, save=False)
        photo.thumbnail.save(thumb.file.name, thumb.file, save=False)
        photo.save()
        with translation.override("es"):
            response = self.client.get(reverse("public:camping_detail", kwargs={"slug": camping.slug}))
        self.assertContains(response, photo.thumbnail.url)
        self.assertContains(response, 'alt="Piscina"')
