"""Manual bookings, units, occupancy calendar, CSV export and the dashboard."""

from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from bookings.emails import send_status_email
from bookings.models import BookingRequest
from campings.pricing import available_units, build_quote

from .factories import future, make_accommodation, make_camping, make_user
from .test_panel import panel_url


def stay(camping, accommodation, arrival, departure, units=1, status=BookingRequest.Status.CONFIRMED, **extra):
    defaults = {"name": "Guest", "email": "guest@example.com"}
    defaults.update(extra)
    return BookingRequest.objects.create(
        camping=camping,
        accommodation=accommodation,
        arrival=arrival,
        departure=departure,
        units=units,
        status=status,
        **defaults,
    )


class UnitsTests(TestCase):
    def setUp(self):
        self.camping = make_camping("Unidades")
        self.pitch = make_accommodation(
            self.camping, kind="pitch", units=5, max_guests=4, base_price=Decimal("20"), price_unit="night"
        )

    def test_confirmed_stays_take_their_units(self):
        stay(self.camping, self.pitch, future(10), future(13), units=3)
        stay(self.camping, self.pitch, future(12), future(14), units=1)
        stay(self.camping, self.pitch, future(10), future(14), units=4, status=BookingRequest.Status.PENDING)
        self.assertEqual(available_units(self.pitch, future(10), future(12)), 2)
        # Night 12 has 3 + 1 units taken.
        self.assertEqual(available_units(self.pitch, future(11), future(14)), 1)
        self.assertEqual(available_units(self.pitch, future(13), future(14)), 4)

    def test_quote_multiplies_price_and_capacity_by_units(self):
        quote = build_quote(self.camping, self.pitch, future(10), future(12), adults=6, units=2)
        self.assertTrue(quote.ok, quote.errors)
        self.assertEqual(quote.total, Decimal("80.00"))  # 2 units × 2 nights × 20
        self.assertIn("2", quote.lines[0].detail)
        too_many = build_quote(self.camping, self.pitch, future(10), future(12), adults=9, units=2)
        self.assertFalse(too_many.ok)

    def test_quote_checks_free_units(self):
        stay(self.camping, self.pitch, future(10), future(12), units=4)
        self.assertTrue(build_quote(self.camping, self.pitch, future(10), future(12), units=1).ok)
        self.assertFalse(build_quote(self.camping, self.pitch, future(10), future(12), units=2).ok)

    def test_hidden_accommodation_only_priced_for_the_panel(self):
        self.pitch.is_active = False
        self.pitch.save()
        self.assertFalse(build_quote(self.camping, self.pitch, future(10), future(12)).ok)
        quote = build_quote(self.camping, self.pitch, future(10), future(12), allow_inactive=True)
        self.assertEqual(quote.total, Decimal("40.00"))


class ManualBookingTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Recepción", owner=self.owner)
        self.acc = make_accommodation(self.camping, units=2, base_price=Decimal("50"), price_unit="night")
        self.client.force_login(self.owner)
        self.url = panel_url("booking_create", self.camping)

    def data(self, **changes):
        data = {
            "accommodation": self.acc.pk,
            "units": 1,
            "arrival": future(10).isoformat(),
            "departure": future(13).isoformat(),
            "adults": 2,
            "children": "",
            "pets": "",
            "status": "confirmed",
            "name": "Walk-in guest",
            "email": "",
            "phone": "+34 600 000 000",
            "country": "",
            "language": "en",
            "internal_notes": "Paid at reception",
        }
        data.update(changes)
        return data

    def test_form_is_prefilled_from_the_calendar(self):
        response = self.client.get(self.url, {"accommodation": self.acc.pk, "arrival": future(5).isoformat()})
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["accommodation"], self.acc.pk)
        self.assertEqual(form.initial["departure"], future(6).isoformat())
        self.assertEqual(form.initial["status"], "confirmed")
        self.assertEqual(form.initial["language"], "es")

    def test_create_confirmed_stay_without_email(self):
        response = self.client.post(self.url, self.data(units=2))
        booking = BookingRequest.objects.get()
        self.assertRedirects(response, panel_url("booking_detail", self.camping, pk=booking.pk))
        self.assertEqual(booking.source, BookingRequest.Source.MANUAL)
        self.assertEqual(booking.status, "confirmed")
        self.assertEqual(booking.units, 2)
        self.assertEqual(booking.children, 0)
        self.assertEqual(booking.estimated_total, Decimal("300.00"))  # 2 units × 3 nights × 50
        self.assertEqual(set(booking.quote), {"es", "en"})
        self.assertEqual(booking.accommodation_name, "Bungalow")
        self.assertEqual(available_units(self.acc, future(10), future(13)), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_agreed_price_replaces_the_calculated_one(self):
        self.client.post(self.url, self.data(total_override="120"))
        booking = BookingRequest.objects.get()
        self.assertEqual(booking.estimated_total, Decimal("120"))
        # Editing keeps the agreed price pre-filled.
        response = self.client.get(panel_url("booking_edit", self.camping, pk=booking.pk))
        self.assertEqual(response.context["form"].initial.get("total_override"), Decimal("120.00"))

    def test_past_dates_and_rules_are_allowed(self):
        today = timezone.localdate()
        arrival, departure = today - timedelta(days=3), today - timedelta(days=2)
        response = self.client.post(self.url, self.data(arrival=arrival.isoformat(), departure=departure.isoformat()))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BookingRequest.objects.get().nights, 1)

    def test_departure_must_follow_arrival(self):
        response = self.client.post(self.url, self.data(departure=future(10).isoformat()))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("departure"))
        self.assertFalse(BookingRequest.objects.exists())

    def test_overbooking_needs_explicit_confirmation(self):
        stay(self.camping, self.acc, future(11), future(12), units=2)
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].overbooking)
        self.assertContains(response, "ignore_availability")
        self.assertEqual(BookingRequest.objects.count(), 1)

        response = self.client.post(self.url, self.data(ignore_availability="on"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BookingRequest.objects.count(), 2)

    def test_pending_stays_do_not_check_availability(self):
        stay(self.camping, self.acc, future(10), future(13), units=2)
        response = self.client.post(self.url, self.data(status="pending"))
        self.assertEqual(response.status_code, 302)

    def test_editing_a_stay_does_not_count_it_twice(self):
        booking = stay(self.camping, self.acc, future(10), future(13), units=2, source="web", language="de")
        response = self.client.post(
            panel_url("booking_edit", self.camping, pk=booking.pk),
            self.data(units=2, departure=future(14).isoformat(), language="de", name="Guest"),
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.departure, future(14))
        self.assertEqual(booking.source, "web")
        self.assertEqual(set(booking.quote), {"es", "de"})

    def test_hidden_accommodation_can_be_booked_from_the_panel(self):
        self.acc.is_active = False
        self.acc.save()
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BookingRequest.objects.get().estimated_total, Decimal("150.00"))

    def test_other_campings_accommodation_is_rejected(self):
        other = make_accommodation(make_camping("Otro"))
        response = self.client.post(self.url, self.data(accommodation=other.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].has_error("accommodation"))

    def test_status_email_is_skipped_without_address(self):
        booking = stay(self.camping, self.acc, future(10), future(13), email="")
        self.assertFalse(send_status_email(booking))
        self.assertEqual(len(mail.outbox), 0)


class BookingListAndExportTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Listado", owner=self.owner)
        self.bungalow = make_accommodation(self.camping, units=3)
        self.pitch = make_accommodation(self.camping, kind="pitch", name={"es": "Parcela"}, units=10)
        self.first = stay(self.camping, self.bungalow, future(5), future(8), name="Ana Pérez", phone="611222333")
        self.second = stay(
            self.camping,
            self.pitch,
            future(7),
            future(9),
            units=2,
            name="Jan de Vries",
            status=BookingRequest.Status.PENDING,
            source=BookingRequest.Source.MANUAL,
        )
        stay(make_camping("Ajeno"), None, future(5), future(8), name="Not mine")
        self.client.force_login(self.owner)

    def test_filters_by_night_accommodation_and_phone(self):
        url = panel_url("bookings", self.camping)
        response = self.client.get(url, {"status": "all", "date": future(7).isoformat()})
        self.assertEqual({b.pk for b in response.context["bookings"]}, {self.first.pk, self.second.pk})
        response = self.client.get(url, {"status": "all", "date": future(8).isoformat()})
        self.assertEqual({b.pk for b in response.context["bookings"]}, {self.second.pk})
        response = self.client.get(url, {"status": "all", "accommodation": self.pitch.pk})
        self.assertEqual({b.pk for b in response.context["bookings"]}, {self.second.pk})
        response = self.client.get(url, {"status": "all", "q": "611222"})
        self.assertEqual({b.pk for b in response.context["bookings"]}, {self.first.pk})

    def test_csv_export(self):
        response = self.client.get(panel_url("booking_export", self.camping), {"status": "all"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertTrue(content.startswith("﻿"))
        rows = [line.split(";") for line in content.lstrip("﻿").splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], "Reference")
        self.assertEqual([row[0] for row in rows[1:]], [self.first.reference, self.second.reference])
        self.assertNotIn("Not mine", content)

    def test_csv_export_respects_filters(self):
        response = self.client.get(panel_url("booking_export", self.camping), {"status": "pending"})
        content = response.content.decode("utf-8")
        self.assertIn(self.second.reference, content)
        self.assertNotIn(self.first.reference, content)


class CalendarTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.camping = make_camping("Calendario", owner=self.owner)
        self.acc = make_accommodation(self.camping, units=2)
        self.client.force_login(self.owner)
        self.month = future(40).replace(day=1)
        self.url = panel_url("calendar", self.camping)

    def cell(self, response, day):
        row = response.context["rows"][0]
        return row["cells"][day - 1]

    def test_levels_per_night(self):
        month = self.month
        stay(self.camping, self.acc, month.replace(day=3), month.replace(day=5))
        stay(self.camping, self.acc, month.replace(day=4), month.replace(day=6))
        stay(self.camping, self.acc, month.replace(day=4), month.replace(day=5), status=BookingRequest.Status.PENDING)
        stay(self.camping, self.acc, month.replace(day=10), month.replace(day=11), units=3)
        response = self.client.get(self.url, {"month": month.strftime("%Y-%m")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.cell(response, 1)["level"], "free")
        self.assertEqual(self.cell(response, 3)["level"], "partial")
        self.assertEqual(self.cell(response, 4)["level"], "full")
        self.assertEqual(self.cell(response, 4)["pending"], 1)
        self.assertEqual(self.cell(response, 5)["level"], "partial")
        self.assertEqual(self.cell(response, 6)["level"], "free")
        self.assertEqual(self.cell(response, 10)["level"], "over")
        day_totals = dict(response.context["day_totals"])
        self.assertEqual(day_totals[month.replace(day=4)], 100)

    def test_invalid_month_falls_back_to_current_month(self):
        response = self.client.get(self.url, {"month": "nonsense"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["days"][0], timezone.localdate().replace(day=1))

    def test_other_campings_are_not_visible(self):
        other = make_camping("Otro", owner=make_user("other@example.com"))
        self.assertEqual(self.client.get(panel_url("calendar", other)).status_code, 404)


class DashboardTodayTests(TestCase):
    def test_arrivals_departures_and_occupancy(self):
        owner = make_user()
        camping = make_camping("Hoy", owner=owner)
        acc = make_accommodation(camping, units=4)
        make_accommodation(camping, units=10, is_active=False)
        today = timezone.localdate()
        arriving = stay(camping, acc, today, today + timedelta(days=2), units=2, adults=2, children=1)
        leaving = stay(camping, acc, today - timedelta(days=2), today, name="Leaving")
        stay(camping, acc, today, today + timedelta(days=1), status=BookingRequest.Status.PENDING)
        self.client.force_login(owner)
        response = self.client.get(panel_url("dashboard", camping))
        data = response.context["today"]
        self.assertEqual(data["arrivals"], [arriving])
        self.assertEqual(data["departures"], [leaving])
        self.assertEqual(data["guests"], 3)
        self.assertEqual((data["units_used"], data["capacity"], data["occupancy"]), (2, 4, 50))
