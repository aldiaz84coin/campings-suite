import json
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from bookings.models import BookingRequest
from campings.models import AccommodationRate, Camping, Facility, Membership, Photo, Season, ServiceRate

from .factories import future, image_file, make_accommodation, make_camping, make_season, make_service, make_user


def panel_url(name, camping, **kwargs):
    with translation.override("en"):
        return reverse(f"panel:{name}", kwargs={"slug": camping.slug, **kwargs})


class AccessTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.camping = make_camping("Mine", owner=self.owner)
        self.other = make_camping("Someone else's", owner=make_user("other@example.com"))

    def test_login_required(self):
        response = self.client.get(panel_url("dashboard", self.camping))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/panel/login/", response["Location"])

    def test_login_with_email_is_case_insensitive(self):
        response = self.client.post("/en/panel/login/", {"username": "OWNER@example.com", "password": "s3cret-pass!"})
        self.assertEqual(response.status_code, 302)

    def test_login_redirects_to_preferred_language(self):
        self.owner.preferred_language = "de"
        self.owner.save()
        response = self.client.post("/en/panel/login/", {"username": "owner@example.com", "password": "s3cret-pass!"})
        self.assertEqual(response["Location"], "/de/panel/")

    def test_single_camping_users_go_straight_to_their_dashboard(self):
        self.client.force_login(self.owner)
        response = self.client.get("/en/panel/")
        self.assertRedirects(response, panel_url("dashboard", self.camping))

    def test_members_cannot_touch_other_campings(self):
        self.client.force_login(self.owner)
        for name in ("dashboard", "profile", "photos", "prices", "bookings", "settings", "team"):
            self.assertEqual(self.client.get(panel_url(name, self.other)).status_code, 404, name)
        acc = make_accommodation(self.other)
        self.assertEqual(self.client.get(panel_url("accommodation_edit", self.camping, pk=acc.pk)).status_code, 404)
        self.assertEqual(self.client.post(panel_url("accommodation_delete", self.camping, pk=acc.pk)).status_code, 404)
        self.assertTrue(acc.__class__.objects.filter(pk=acc.pk).exists())

    def test_staff_cannot_change_owner_settings(self):
        staff = make_user("staff@example.com")
        Membership.objects.create(user=staff, camping=self.camping, role=Membership.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(panel_url("profile", self.camping)).status_code, 200)
        self.assertEqual(self.client.get(panel_url("settings", self.camping)).status_code, 403)
        self.assertEqual(self.client.post(panel_url("publish", self.camping)).status_code, 403)

    def test_superuser_can_manage_every_camping(self):
        admin = make_user("admin@example.com", is_superuser=True, is_staff=True)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(panel_url("dashboard", self.other)).status_code, 200)
        self.assertEqual(self.client.get("/en/panel/platform/").status_code, 200)

    def test_platform_is_superuser_only(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/en/panel/platform/").status_code, 403)


class CampingEditingTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Editable", owner=self.owner, languages=["es", "en"])
        self.client.force_login(self.owner)

    def test_every_page_renders(self):
        acc = make_accommodation(self.camping)
        service = make_service(self.camping)
        season = make_season(self.camping, future(1), future(30))
        facility = self.camping.facilities.create(kind="custom", name={"es": "Kayak"})
        booking = BookingRequest.objects.create(
            camping=self.camping, accommodation=acc, arrival=future(3), departure=future(5), name="G", email="g@example.com"
        )
        pages = [
            ("dashboard", {}), ("profile", {}), ("location", {}), ("appearance", {}), ("settings", {}), ("photos", {}),
            ("facilities", {}), ("facility_create", {}), ("facility_edit", {"pk": facility.pk}),
            ("accommodations", {}), ("accommodation_create", {}), ("accommodation_edit", {"pk": acc.pk}),
            ("services", {}), ("service_create", {}), ("service_edit", {"pk": service.pk}),
            ("seasons", {}), ("season_create", {}), ("season_edit", {"pk": season.pk}),
            ("prices", {}), ("policies", {}), ("bookings", {}), ("booking_detail", {"pk": booking.pk}), ("team", {}),
        ]
        for name, kwargs in pages:
            for language in ("es", "en", "de"):
                with translation.override(language):
                    url = reverse(f"panel:{name}", kwargs={"slug": self.camping.slug, **kwargs})
                self.assertEqual(self.client.get(url).status_code, 200, url)
        for url in ("/es/panel/account/", "/es/panel/account/password/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_profile_update_with_translations(self):
        response = self.client.post(
            panel_url("profile", self.camping),
            {"name": "Nuevo nombre", "tagline_es": "Hola", "tagline_en": "Hi", "description_es": "Texto", "stars": "3"},
        )
        self.assertEqual(response.status_code, 302)
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.name, "Nuevo nombre")
        self.assertEqual(self.camping.tagline, {"es": "Hola", "en": "Hi"})
        self.assertEqual(self.camping.stars, 3)

    def test_settings_change_languages_and_slug(self):
        response = self.client.post(
            panel_url("settings", self.camping),
            {"slug": "nuevo-slug", "default_language": "fr", "languages": ["en", "de"], "currency": "EUR",
             "accepts_booking_requests": "on"},
        )
        self.assertRedirects(response, "/en/panel/c/nuevo-slug/settings/", fetch_redirect_response=False)
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.languages, ["fr", "en", "de"])

    def test_owner_cannot_set_custom_domain(self):
        self.client.post(
            panel_url("settings", self.camping),
            {"slug": self.camping.slug, "default_language": "es", "languages": ["es"], "currency": "EUR",
             "custom_domain": "www.hack.test"},
        )
        self.camping.refresh_from_db()
        self.assertIsNone(self.camping.custom_domain)

    def test_reserved_slug_is_rejected(self):
        response = self.client.post(
            panel_url("settings", self.camping),
            {"slug": "panel", "default_language": "es", "languages": ["es"], "currency": "EUR"},
        )
        self.assertEqual(response.status_code, 200)

    def test_publish_toggle(self):
        self.camping.is_published = False
        self.camping.save()
        self.client.post(panel_url("publish", self.camping))
        self.camping.refresh_from_db()
        self.assertTrue(self.camping.is_published)

    def test_facility_checklist(self):
        self.client.post(panel_url("facilities", self.camping), {"facilities": ["pool", "wifi", "bogus"], "paid": ["wifi"]})
        kinds = dict(self.camping.facilities.values_list("kind", "is_paid"))
        self.assertEqual(kinds, {"pool": False, "wifi": True})
        self.client.post(panel_url("facilities", self.camping), {"facilities": ["pool"]})
        self.assertEqual(list(self.camping.facilities.values_list("kind", flat=True)), ["pool"])

    def test_custom_facility_needs_a_name(self):
        response = self.client.post(panel_url("facility_create", self.camping), {"description_es": "x"})
        self.assertEqual(response.status_code, 200)
        self.client.post(panel_url("facility_create", self.camping), {"name_es": "Kayak", "icon": "ticket"})
        self.assertTrue(self.camping.facilities.filter(kind=Facility.CUSTOM).exists())

    def test_accommodation_create_with_amenities_and_photos(self):
        photo = self.make_photo()
        response = self.client.post(
            panel_url("accommodation_create", self.camping),
            {"kind": "bungalow", "name_es": "Bungalow Mar", "max_guests": 4, "units": 3, "base_price": "80,5".replace(",", "."),
             "price_unit": "night", "amenities": ["kitchen", "wifi"], "photos": [photo.pk], "is_active": "on", "position": ""},
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)
        acc = self.camping.accommodations.get()
        self.assertEqual(acc.amenities, ["kitchen", "wifi"])
        self.assertEqual(acc.base_price, Decimal("80.50"))
        photo.refresh_from_db()
        self.assertEqual(photo.accommodation, acc)

    def test_accommodation_requires_name_in_main_language(self):
        response = self.client.post(
            panel_url("accommodation_create", self.camping),
            {"kind": "pitch", "name_en": "Only English", "max_guests": 4, "units": 1, "base_price": "10", "price_unit": "night"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)

    def test_season_overlap_is_rejected(self):
        make_season(self.camping, future(10), future(20))
        response = self.client.post(
            panel_url("season_create", self.camping),
            {"name_es": "Otra", "start_date": future(15).isoformat(), "end_date": future(25).isoformat(), "color": "#123456"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.camping.seasons.count(), 1)

    def test_copy_seasons_to_next_year(self):
        season = make_season(self.camping, future(10), future(20), min_nights=3)
        acc = make_accommodation(self.camping)
        AccommodationRate.objects.create(accommodation=acc, season=season, price=Decimal("99"))
        self.client.post(panel_url("seasons_copy", self.camping))
        copy = Season.objects.exclude(pk=season.pk).get()
        self.assertEqual(copy.start_date.year, season.start_date.year + 1)
        self.assertEqual(copy.min_nights, 3)
        self.assertEqual(copy.accommodation_rates.get().price, Decimal("99"))

    def test_price_matrix(self):
        acc = make_accommodation(self.camping)
        service = make_service(self.camping)
        season = make_season(self.camping, future(1), future(30))
        response = self.client.post(
            panel_url("prices", self.camping),
            {f"acc-{acc.pk}-base": "55", f"acc-{acc.pk}-{season.pk}": "70,50", f"svc-{service.pk}-base": "6",
             f"svc-{service.pk}-{season.pk}": ""},
        )
        self.assertEqual(response.status_code, 302)
        acc.refresh_from_db()
        self.assertEqual(acc.base_price, Decimal("55"))
        self.assertEqual(AccommodationRate.objects.get().price, Decimal("70.50"))
        self.assertFalse(ServiceRate.objects.exists())
        # Clearing a cell removes the seasonal price.
        self.client.post(panel_url("prices", self.camping), {f"acc-{acc.pk}-base": "55", f"acc-{acc.pk}-{season.pk}": ""})
        self.assertFalse(AccommodationRate.objects.exists())

    def test_invalid_price_is_reported(self):
        acc = make_accommodation(self.camping)
        response = self.client.post(panel_url("prices", self.camping), {f"acc-{acc.pk}-base": "-5"}, follow=True)
        self.assertEqual(len(list(response.context["messages"])), 1)
        acc.refresh_from_db()
        self.assertEqual(acc.base_price, Decimal("50"))

    def test_policy_update(self):
        response = self.client.post(
            panel_url("policies", self.camping),
            {"check_in_from": "15:00", "check_out_until": "11:00", "min_nights": 2, "min_age": 18, "deposit_percent": 20,
             "payment_methods": ["card", "bizum"], "refundable": "on", "free_cancellation_days": 7,
             "cancellation_fee_percent": 50, "pets_allowed": "on", "rules_text_es": "Silencio"},
        )
        self.assertEqual(response.status_code, 302)
        policy = Camping.objects.get(pk=self.camping.pk).get_policy()
        self.assertEqual(policy.deposit_percent, 20)
        self.assertEqual(policy.payment_methods, ["card", "bizum"])
        self.assertEqual(policy.rules_text, {"es": "Silencio"})

    def make_photo(self):
        self.client.post(panel_url("photos", self.camping), {"images": [image_file()]})
        return self.camping.photos.latest("id")


class PhotoTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Fotos", owner=self.owner)
        self.client.force_login(self.owner)
        self.url = panel_url("photos", self.camping)

    def test_upload_resizes_and_converts_to_webp(self):
        response = self.client.post(self.url, {"images": [image_file(size=(4000, 3000)), image_file("b.png", fmt="PNG")]})
        self.assertEqual(response.status_code, 302)
        photos = list(self.camping.photos.all())
        self.assertEqual(len(photos), 2)
        first = photos[0]
        self.assertEqual((first.width, first.height), (2000, 1500))
        self.assertTrue(first.image.name.endswith(".webp"))
        self.assertTrue(first.thumbnail.name.endswith(".webp"))
        self.assertEqual([p.position for p in photos], [1, 2])

    def test_ajax_upload_returns_json_and_rejects_non_images(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
        response = self.client.post(self.url, {"images": [bad]}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        response = self.client.post(self.url, {"images": [image_file()]}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertTrue(response.json()["ok"])

    def test_reorder_cover_and_delete(self):
        for _ in range(3):
            self.client.post(self.url, {"images": [image_file()]})
        a, b, c = self.camping.photos.all()
        self.client.post(panel_url("photo_reorder", self.camping), json.dumps({"order": [c.pk, a.pk, b.pk]}),
                         content_type="application/json")
        self.assertEqual(list(self.camping.photos.values_list("pk", flat=True)), [c.pk, a.pk, b.pk])
        self.client.post(panel_url("photo_cover", self.camping, pk=b.pk))
        self.assertEqual(self.camping.cover_photo, b)
        storage, name = b.image.storage, b.image.name
        self.client.post(panel_url("photo_delete", self.camping, pk=b.pk))
        self.assertFalse(Photo.objects.filter(pk=b.pk).exists())
        self.assertTrue(storage.exists(c.image.name))
        self.assertIsNotNone(name)

    def test_cannot_reorder_other_campings_photos(self):
        other = make_camping("Otro", owner=make_user("x@example.com"))
        response = self.client.post(panel_url("photo_reorder", other), json.dumps({"order": []}), content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_logo_upload(self):
        response = self.client.post(
            panel_url("appearance", self.camping),
            {"primary_color": "#123456", "accent_color": "#abcdef", "font_style": "classic", "logo_file": image_file("logo.png", fmt="PNG")},
        )
        self.assertEqual(response.status_code, 302)
        self.camping.refresh_from_db()
        self.assertTrue(self.camping.logo.name.endswith(".webp"))
        self.assertEqual(self.camping.primary_color, "#123456")

    def test_invalid_colour_is_rejected(self):
        response = self.client.post(
            panel_url("appearance", self.camping),
            {"primary_color": "red;}body{display:none", "accent_color": "#abcdef", "font_style": "modern"},
        )
        self.assertEqual(response.status_code, 200)
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.primary_color, "#2f6f4e")


class BookingManagementTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Reservas", owner=self.owner)
        self.acc = make_accommodation(self.camping)
        self.booking = BookingRequest.objects.create(
            camping=self.camping, accommodation=self.acc, arrival=future(10), departure=future(12),
            name="Guest", email="guest@example.com", language="de",
        )
        self.client.force_login(self.owner)

    def test_confirm_sends_email_in_guest_language(self):
        url = panel_url("booking_detail", self.camping, pk=self.booking.pk)
        response = self.client.post(url, {"status": ["pending", "confirmed"], "internal_notes": "", "notify_guest": "on"})
        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "confirmed")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["guest@example.com"])

    def test_no_email_when_not_requested(self):
        url = panel_url("booking_detail", self.camping, pk=self.booking.pk)
        self.client.post(url, {"status": "declined", "internal_notes": "full"})
        self.assertEqual(len(mail.outbox), 0)

    def test_list_filters(self):
        response = self.client.get(panel_url("bookings", self.camping), {"status": "pending", "q": "guest"})
        self.assertContains(response, self.booking.reference)
        response = self.client.get(panel_url("bookings", self.camping), {"status": "confirmed"})
        self.assertNotContains(response, self.booking.reference)


class SignupAndTeamTests(TestCase):
    def test_signup_creates_user_camping_and_membership(self):
        response = self.client.post(
            "/fr/panel/signup/",
            {"camping_name": "Camping du Lac", "first_name": "Luc", "email": "Luc@Example.com",
             "password1": "a-very-safe-pass-9", "password2": "a-very-safe-pass-9", "accept_terms": "on"},
        )
        camping = Camping.objects.get(name="Camping du Lac")
        self.assertRedirects(response, f"/fr/panel/c/{camping.slug}/", fetch_redirect_response=False)
        self.assertFalse(camping.is_approved)  # SIGNUP_REQUIRES_APPROVAL
        self.assertEqual(camping.default_language, "fr")
        self.assertTrue(camping.memberships.filter(user__email="luc@example.com", role="owner").exists())

    def test_signup_rejects_duplicate_email(self):
        make_user("taken@example.com")
        response = self.client.post(
            "/es/panel/signup/",
            {"camping_name": "X", "first_name": "Y", "email": "TAKEN@example.com", "password1": "a-very-safe-pass-9",
             "password2": "a-very-safe-pass-9", "accept_terms": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)

    def test_invite_new_member_gets_a_password_link(self):
        owner = make_user()
        camping = make_camping("Equipo", owner=owner)
        self.client.force_login(owner)
        response = self.client.post(panel_url("team", camping), {"email": "new@example.com", "role": "staff"})
        self.assertEqual(response.status_code, 200)
        link = response.context["invite_link"]
        self.assertIn("/panel/password/reset/", link)
        self.assertEqual(len(mail.outbox), 1)
        self.client.logout()
        # Follow the invitation and choose a password.
        response = self.client.get(link, follow=True)
        form_url = response.redirect_chain[-1][0]
        response = self.client.post(form_url, {"new_password1": "another-safe-pass-7", "new_password2": "another-safe-pass-7"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.login(email="new@example.com", password="another-safe-pass-7"))

    def test_last_owner_cannot_be_removed(self):
        owner = make_user()
        camping = make_camping("Equipo", owner=owner)
        self.client.force_login(owner)
        membership = camping.memberships.get()
        self.client.post(panel_url("team_remove", camping, pk=membership.pk))
        self.assertTrue(camping.memberships.exists())

    def test_platform_creates_camping_with_owner(self):
        admin = make_user("admin@example.com", is_superuser=True, is_staff=True)
        self.client.force_login(admin)
        response = self.client.post("/es/panel/platform/new/", {"name": "Nuevo", "owner_email": "own@example.com", "default_language": "es"})
        self.assertEqual(response.status_code, 302)
        camping = Camping.objects.get(name="Nuevo")
        self.assertTrue(camping.is_approved)
        self.assertTrue(camping.memberships.filter(user__email="own@example.com", role="owner").exists())

    def test_platform_approval_toggle(self):
        admin = make_user("admin@example.com", is_superuser=True, is_staff=True)
        camping = make_camping("Pendiente", is_approved=False)
        self.client.force_login(admin)
        self.client.post(f"/es/panel/platform/{camping.slug}/approval/", {"next": "https://evil.example/"})
        camping.refresh_from_db()
        self.assertTrue(camping.is_approved)
