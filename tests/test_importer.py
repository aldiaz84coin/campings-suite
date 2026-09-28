"""Importing a camping's details, photos and prices from its current website."""

import threading
from datetime import date
from decimal import Decimal
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from campings.models import Camping, Facility, Season
from importer import apply as apply_module
from importer import service
from importer.dates import find_periods, main_year
from importer.fetch import Fetched, FetchError, fetch, normalize_url
from importer.models import SiteImport
from importer.prices import classify
from importer.text import looks_like_price, parse_money

from .factories import make_camping, make_user
from .test_panel import panel_url

SITE = Path(__file__).parent / "fixtures" / "camping_site"
TODAY = date(2026, 3, 1)


def jpeg_bytes(size=(1200, 800)):
    buffer = BytesIO()
    Image.new("RGB", size, (30, 120, 170)).save(buffer, "JPEG")
    return buffer.getvalue()


def png_bytes():
    buffer = BytesIO()
    Image.new("RGBA", (400, 160), (200, 40, 40, 255)).save(buffer, "PNG")
    return buffer.getvalue()


class FakeWeb:
    """Serves the fixture website instead of the internet."""

    def __init__(self):
        self.requested = []

    def __call__(self, url, *, max_bytes, accept="", timeout=10):
        self.requested.append(url)
        path = urlsplit(url).path
        if "foto-rota" in path:
            raise FetchError("404")
        if path.endswith((".jpg", ".jpeg")):
            if "-1024x683" not in path and "piscina.jpg" in path:
                raise FetchError("404")  # no original for this one: the resized copy is used
            return Fetched(url, 200, "image/jpeg", None, jpeg_bytes())
        if path.endswith(".png"):
            return Fetched(url, 200, "image/png", None, png_bytes())
        file = SITE / (path.strip("/") or "index.html")
        if file.is_dir():
            file = file / "index.html"
        if not file.suffix:
            file = file.with_suffix(".html")
        if not file.exists():
            raise FetchError("404")
        return Fetched(url, 200, "text/html", "utf-8", file.read_bytes())


class ParserTests(SimpleTestCase):
    def test_periods_in_several_languages(self):
        cases = {
            "Temporada alta: del 1 de julio al 31 de agosto": [(date(2026, 7, 1), date(2026, 8, 31))],
            "T. Baja 01/04 - 30/06 y 01/09 - 30/09": [
                (date(2026, 4, 1), date(2026, 6, 30)),
                (date(2026, 9, 1), date(2026, 9, 30)),
            ],
            "High season July 1 – August 31": [(date(2026, 7, 1), date(2026, 8, 31))],
            "du 1er au 15 juillet": [(date(2026, 7, 1), date(2026, 7, 15))],
            "Hauptsaison 1. Juli bis 31. August 2027": [(date(2027, 7, 1), date(2027, 8, 31))],
            "van 1 juli t/m 31 augustus": [(date(2026, 7, 1), date(2026, 8, 31))],
            "dal 1 luglio al 31 agosto": [(date(2026, 7, 1), date(2026, 8, 31))],
            "Navidad: del 20 de diciembre al 6 de enero": [(date(2026, 12, 20), date(2027, 1, 6))],
            "01.07. - 31.08.": [(date(2026, 7, 1), date(2026, 8, 31))],
        }
        for text, expected in cases.items():
            self.assertEqual(find_periods(text, TODAY), expected, text)

    def test_prices_and_group_sizes_are_not_dates(self):
        for text in ("Parcela 2-4 personas 25,50 €", "Adultos 6.50 - 7.50 €", "Tel. 972 81 23 45"):
            self.assertEqual(find_periods(text, TODAY), [], text)

    def test_past_dates_without_year_move_to_next_year(self):
        self.assertEqual(find_periods("1 de enero al 15 de febrero", TODAY), [(date(2027, 1, 1), date(2027, 2, 15))])
        self.assertEqual(main_year("Tarifas 2027 · precios 2027 (2026)", TODAY), 2027)

    def test_money(self):
        self.assertEqual(parse_money("6,50 €"), Decimal("6.50"))
        self.assertEqual(parse_money("€ 12.5"), Decimal("12.50"))
        self.assertEqual(parse_money("1.200,00€"), Decimal("1200.00"))
        self.assertEqual(parse_money("Gratis"), Decimal("0.00"))
        self.assertIsNone(parse_money("Consultar"))
        self.assertTrue(looks_like_price("12 €/noche"))
        self.assertFalse(looks_like_price("Temporada alta"))

    def test_classification(self):
        self.assertEqual(classify("Parcela (coche + tienda)")["accommodation_kind"], "pitch")
        self.assertEqual(classify("Bungalow 4 pers.")["max_guests"], 4)
        self.assertEqual(classify("Adulto")["unit"], "adult_night")
        self.assertEqual(classify("Tasa turística por adulto")["icon"], "receipt")
        self.assertEqual(classify("Caravana")["kind"], "service")
        self.assertEqual(classify("Caravana de alquiler")["kind"], "accommodation")
        self.assertEqual(classify("Electricity 10A")["mode"], "optional")


class ExtractionTests(TestCase):
    def read(self):
        web = FakeWeb()
        with mock.patch.object(service, "fetch", web):
            home = service.fetch_page("https://www.marblava.test/", "home")
            pages = [home]
            for url, role in service.choose_links(home):
                try:
                    pages.append(service.fetch_page(url, role))
                except FetchError:
                    pass
            alternates = {"en": service.fetch_page("https://www.marblava.test/en/", "home")}
            return service.build_data(pages, alternates, TODAY)

    def test_details_texts_and_contact(self):
        data = self.read()
        fields = data["fields"]
        self.assertEqual(fields["name"], "Camping Mar Blava")
        self.assertEqual(fields["email"], "info@marblava.test")
        self.assertEqual(fields["phone"], "972 81 23 45")
        self.assertEqual(fields["whatsapp"], "+34600111222")
        self.assertEqual(fields["instagram"], "https://www.instagram.com/campingmarblava/")
        self.assertEqual(
            (fields["postal_code"], fields["city"], fields["country"]), ("17250", "Platja d'Aro", "España")
        )
        self.assertEqual((fields["latitude"], fields["longitude"]), (41.8123, 3.0654))
        self.assertEqual(fields["stars"], 3)
        self.assertEqual((fields["check_in_from"], fields["check_out_until"]), ("15:00", "12:00"))
        self.assertEqual((fields["opening_date"], fields["closing_date"]), ("2026-04-01", "2026-10-12"))
        self.assertIn("200 metros de la playa", data["texts"]["es"]["description"])
        self.assertNotIn("cookies", data["texts"]["es"]["description"])
        self.assertIn("200 metres from the beach", data["texts"]["en"]["description"])
        self.assertIn("AP-7", data["location_info"]["es"])
        self.assertTrue(data["logo"].endswith("logo-mar-blava.png"))

    def test_photos_and_facilities(self):
        data = self.read()
        urls = [photo["url"] for photo in data["photos"]]
        self.assertTrue(any("playa-atardecer.jpg" in url for url in urls))
        self.assertFalse(any("-300x200" in url for url in urls), urls)
        self.assertFalse(any("icon" in url or "tripadvisor" in url or "logo" in url for url in urls), urls)
        pool = next(photo for photo in data["photos"] if "piscina" in photo["url"])
        self.assertEqual(pool["alt"], "Piscina del camping")
        self.assertTrue(pool["original"].endswith("piscina.jpg"))
        for key in ("pool", "kids_pool", "restaurant", "bar", "wifi", "laundry", "playground", "pets", "bbq"):
            self.assertIn(key, data["facilities"], key)
        self.assertNotIn("tennis", data["facilities"])

    def test_seasons_and_prices(self):
        data = self.read()
        seasons = {season["kind"]: season for season in data["seasons"]}
        self.assertEqual(set(seasons), {"low", "mid", "high", "special"})
        self.assertEqual(seasons["low"]["name"], "Temporada Baja")
        self.assertEqual(seasons["low"]["periods"], [["2026-04-01", "2026-06-14"], ["2026-09-16", "2026-10-12"]])
        self.assertEqual(seasons["special"]["periods"], [["2026-04-02", "2026-04-06"]])
        items = {item["label"]: item for item in data["items"]}
        pitch = items["Parcela (coche + tienda o caravana)"]
        self.assertEqual(
            (pitch["kind"], pitch["accommodation_kind"], pitch["base"]), ("accommodation", "pitch", "12.50")
        )
        self.assertEqual(pitch["prices"][seasons["high"]["key"]], "26.00")
        bungalow = items["Bungalow Pino (4 pers.)"]
        self.assertEqual((bungalow["accommodation_kind"], bungalow["max_guests"]), ("bungalow", 4))
        self.assertEqual(bungalow["prices"][seasons["special"]["key"]], "110.00")
        self.assertEqual((items["Adulto"]["unit"], items["Adulto"]["mode"]), ("adult_night", "mandatory"))
        self.assertEqual(items["Tasa turística"]["base"], "0.50")
        self.assertEqual(data["pdfs"], ["https://www.marblava.test/wp-content/uploads/tarifas-2026.pdf"])


class ImportFlowTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", is_superuser=True, is_staff=True)
        self.client.force_login(self.admin)
        self.web = FakeWeb()
        patches = [
            mock.patch.object(service, "fetch", self.web),
            mock.patch.object(apply_module, "fetch", self.web),
            mock.patch("importer.service.timezone.localdate", return_value=TODAY),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def create_with_website(self):
        response = self.client.post(
            "/es/panel/platform/new/",
            {
                "name": "Mar Blava",
                "owner_email": "owner@marblava.test",
                "default_language": "es",
                "website_url": "www.marblava.test",
            },
        )
        camping = Camping.objects.get(name="Mar Blava")
        site_import = SiteImport.objects.get(camping=camping)
        self.assertRedirects(
            response, f"/es/panel/c/{camping.slug}/import/{site_import.pk}/", fetch_redirect_response=False
        )
        return camping, site_import

    def test_create_camping_from_its_website(self):
        camping, site_import = self.create_with_website()
        self.assertEqual(site_import.url, "https://www.marblava.test/")
        response = self.client.get(f"/es/panel/c/{camping.slug}/import/{site_import.pk}/")
        self.assertContains(response, "Temporada Baja")
        self.assertContains(response, "info@marblava.test")
        self.assertContains(response, "tarifas-2026.pdf")
        data = site_import.data
        post = {
            "field": ["email", "phone", "address", "postal_code", "city", "region", "country", "location", "stars"]
            + ["opening", "check_in_from", "check_out_until", "instagram"],
            "text": ["es:tagline", "es:description", "en:description"],
            "location_info": "1",
            "facility": ["pool", "wifi", "restaurant"],
            "season": [season["key"] for season in data["seasons"]],
            "item": [item["key"] for item in data["items"]],
            "photo": [str(index) for index, photo in enumerate(data["photos"]) if "foto-rota" not in photo["url"]][:4],
            "logo": "1",
        }
        for item in data["items"]:
            if item["label"] == "Moto":
                post[f"item_mode_{item['key']}"] = "optional"
        response = self.client.post(f"/es/panel/c/{camping.slug}/import/{site_import.pk}/", post)
        self.assertRedirects(
            response, f"/es/panel/c/{camping.slug}/import/{site_import.pk}/photos/", fetch_redirect_response=False
        )
        camping.refresh_from_db()
        self.assertEqual(camping.email, "info@marblava.test")
        self.assertEqual(camping.city, "Platja d'Aro")
        self.assertEqual(camping.stars, 3)
        self.assertEqual((camping.latitude, camping.longitude), (Decimal("41.812300"), Decimal("3.065400")))
        self.assertEqual((camping.opening_date, camping.closing_date), (date(2026, 4, 1), date(2026, 10, 12)))
        self.assertIn("en", camping.languages)
        self.assertIn("200 metres", camping.description["en"])
        self.assertIn("AP-7", camping.location_info["es"])
        policy = camping.get_policy()
        self.assertEqual(policy.check_in_from.strftime("%H:%M"), "15:00")
        self.assertEqual(set(camping.facilities.values_list("kind", flat=True)), {"pool", "wifi", "restaurant"})

        seasons = {season.kind: season for season in camping.seasons.prefetch_related("periods")}
        self.assertEqual(set(seasons), {"low", "mid", "high", "special"})
        self.assertEqual(seasons["low"].periods.count(), 2)
        self.assertEqual(seasons["high"].name, {"es": "Temporada Alta"})
        pitch = camping.accommodations.get(kind="pitch")
        self.assertEqual(pitch.base_price, Decimal("12.50"))
        self.assertEqual(pitch.rates.get(season=seasons["high"]).price, Decimal("26.00"))
        self.assertEqual(camping.accommodations.count(), 3)
        adult = camping.services.get(name__es="Adulto")
        self.assertEqual((adult.unit, adult.mode, adult.icon), ("adult_night", "mandatory", "user"))
        self.assertEqual(adult.rates.get(season=seasons["special"]).price, Decimal("6.50"))

        # Photos (and the logo) are downloaded in batches.
        url = f"/es/panel/c/{camping.slug}/import/{site_import.pk}/photos/"
        self.assertContains(self.client.get(url), "data-photo-import")
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="fetch")
        result = response.json()
        while result["remaining"]:
            result = self.client.post(url, HTTP_X_REQUESTED_WITH="fetch").json()
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["failed"], 0)
        camping.refresh_from_db()
        self.assertTrue(camping.logo)
        self.assertEqual(camping.photos.count(), 4)
        self.assertTrue(camping.photos.filter(caption__es="Piscina del camping").exists())

        # Quotes use the imported seasons.
        from campings.pricing import build_quote

        quote = build_quote(camping, pitch, date(2026, 7, 20), date(2026, 7, 22), adults=2)
        self.assertEqual(quote.total, Decimal("86.00"))  # 2 nights × (26 pitch + 2 × 8 adults + 2 × 0.50 tax)

    def test_broken_photo_is_counted_and_skipped(self):
        camping, site_import = self.create_with_website()
        broken = next(index for index, photo in enumerate(site_import.data["photos"]) if "foto-rota" in photo["url"])
        self.client.post(f"/es/panel/c/{camping.slug}/import/{site_import.pk}/", {"photo": [str(broken)]})
        url = f"/es/panel/c/{camping.slug}/import/{site_import.pk}/photos/"
        result = self.client.post(url, HTTP_X_REQUESTED_WITH="fetch").json()
        self.assertEqual((result["done"], result["failed"], result["remaining"]), (0, 1, 0))

    def test_unreadable_website_still_creates_the_camping(self):
        response = self.client.post(
            "/es/panel/platform/new/",
            {
                "name": "Sin web",
                "owner_email": "owner@sinweb.test",
                "default_language": "es",
                "website_url": "https://www.no-existe.test/pagina-que-no-existe/",
            },
            follow=True,
        )
        camping = Camping.objects.get(name="Sin web")
        self.assertEqual(response.redirect_chain[-1][0], f"/es/panel/c/{camping.slug}/settings/")
        self.assertContains(response, "no-existe")
        self.assertFalse(SiteImport.objects.exists())

    def test_import_page_for_existing_camping(self):
        camping = make_camping("Existente", owner=make_user("owner@example.com"))
        Facility.objects.create(camping=camping, kind="pool")
        response = self.client.post(panel_url("import", camping), {"url": "https://www.marblava.test/"})
        site_import = SiteImport.objects.get(camping=camping)
        self.assertRedirects(
            response, panel_url("import_review", camping, pk=site_import.pk), fetch_redirect_response=False
        )
        response = self.client.get(panel_url("import_review", camping, pk=site_import.pk))
        self.assertContains(response, "already added")
        # Staff members cannot import.
        staff = make_user("staff@example.com")
        camping.memberships.create(user=staff, role="staff")
        self.client.force_login(staff)
        self.assertEqual(self.client.get(panel_url("import", camping)).status_code, 403)

    def test_applied_import_cannot_be_applied_twice(self):
        camping, site_import = self.create_with_website()
        url = f"/es/panel/c/{camping.slug}/import/{site_import.pk}/"
        self.client.post(url, {"season": [site_import.data["seasons"][0]["key"]]})
        self.client.post(url, {"season": [site_import.data["seasons"][0]["key"]]})
        self.assertEqual(Season.objects.filter(camping=camping).count(), 1)


class FetchSafetyTests(SimpleTestCase):
    def test_urls_are_normalised(self):
        self.assertEqual(normalize_url("www.camping.test"), "https://www.camping.test/")
        with self.assertRaises(FetchError):
            normalize_url("ftp://www.camping.test/")
        with self.assertRaises(FetchError):
            normalize_url("")

    def test_private_addresses_are_refused(self):
        for url in (
            "http://127.0.0.1/",
            "http://localhost:8000/",
            "http://169.254.169.254/latest/",
            "http://10.0.0.5/",
        ):
            with self.assertRaises(FetchError, msg=url):
                fetch(url, max_bytes=1000)


class LocalServerTests(SimpleTestCase):
    """The real HTTP client against a local web server (private addresses allowed here)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(SITE), **kwargs)

            def do_GET(self):  # noqa: N802
                if self.path == "/old/":
                    self.send_response(301)
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if self.path.endswith(".jpg"):
                    body = jpeg_bytes((300, 200))
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    @override_settings(IMPORTER_ALLOW_PRIVATE_HOSTS=True)
    def test_fetch_follows_redirects_and_limits_size(self):
        page = fetch(f"{self.base}/old/", max_bytes=1_000_000)
        self.assertEqual(page.url, f"{self.base}/")
        self.assertTrue(page.is_html)
        self.assertIn("Camping Mar Blava", page.text())
        image = fetch(f"{self.base}/photo.jpg", max_bytes=1_000_000, accept="image/*")
        self.assertEqual(image.content_type, "image/jpeg")
        with self.assertRaises(FetchError):
            fetch(f"{self.base}/", max_bytes=500)
        with self.assertRaises(FetchError):
            fetch(f"{self.base}/missing.html", max_bytes=1_000_000)

    def test_local_server_is_refused_by_default(self):
        with self.assertRaises(FetchError):
            fetch(f"{self.base}/", max_bytes=1_000_000)
