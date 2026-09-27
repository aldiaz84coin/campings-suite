from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import translation

from bookings.models import BookingRequest
from campings.models import AccommodationRate, ServiceRate
from campings.pricing import available_units, build_quote

from .factories import future, make_accommodation, make_camping, make_season, make_service


class QuoteTests(TestCase):
    def setUp(self):
        self.camping = make_camping(open_all_year=True)
        self.policy = self.camping.get_policy()
        self.acc = make_accommodation(self.camping, kind="pitch", base_price=Decimal("20"), max_guests=4, units=2)

    def quote(self, arrival, departure, **kwargs):
        with translation.override("en"):
            return build_quote(self.camping, self.acc, arrival, departure, **kwargs)

    def test_base_price_without_seasons(self):
        quote = self.quote(future(10), future(13), adults=2)
        self.assertTrue(quote.ok, quote.errors)
        self.assertEqual(quote.nights, 3)
        self.assertEqual(quote.total, Decimal("60.00"))

    def test_nights_are_priced_by_season(self):
        season = make_season(self.camping, future(12), future(20))
        AccommodationRate.objects.create(accommodation=self.acc, season=season, price=Decimal("35"))
        quote = self.quote(future(10), future(14), adults=2)  # 2 nights base + 2 nights season
        self.assertEqual(quote.total, Decimal("110.00"))
        self.assertEqual(len(quote.lines), 2)

    def test_mandatory_and_optional_services(self):
        make_service(self.camping, price=Decimal("5"), unit="adult_night", mode="mandatory")
        make_service(self.camping, name={"en": "Child"}, price=Decimal("3"), unit="child_night", mode="mandatory")
        linen = make_service(self.camping, name={"en": "Linen"}, price=Decimal("10"), unit="stay", mode="optional")
        make_service(self.camping, name={"en": "Wi-Fi"}, price=Decimal("99"), unit="stay", mode="included")
        quote = self.quote(future(10), future(12), adults=2, children=1)
        # 2 nights x 20 + 2 adults x 2 nights x 5 + 1 child x 2 nights x 3
        self.assertEqual(quote.total, Decimal("66.00"))
        quote = self.quote(future(10), future(12), adults=2, children=1, extras=[linen])
        self.assertEqual(quote.total, Decimal("76.00"))

    def test_seasonal_service_price_and_per_person_accommodation(self):
        season = make_season(self.camping, future(1), future(60))
        adult = make_service(self.camping, price=Decimal("5"))
        ServiceRate.objects.create(service=adult, season=season, price=Decimal("7"))
        self.acc.price_unit = "person_night"
        self.acc.save()
        quote = self.quote(future(10), future(11), adults=2, children=1)
        # 20 x 3 people + 7 x 2 adults
        self.assertEqual(quote.total, Decimal("74.00"))

    def test_service_limited_to_some_accommodations(self):
        other = make_accommodation(self.camping)
        adult = make_service(self.camping, price=Decimal("5"))
        adult.accommodations.add(other)
        quote = self.quote(future(10), future(11), adults=2)
        self.assertEqual(quote.total, Decimal("20.00"))

    def test_validation_errors(self):
        self.policy.min_nights = 3
        self.policy.pets_allowed = False
        self.policy.save()
        self.camping._policy_cache = None
        quote = self.quote(future(10), future(11), adults=0, children=5, pets=1)
        messages = " ".join(str(e) for e in quote.errors)
        self.assertIn("minimum stay", messages)
        self.assertIn("At least one adult", messages)
        self.assertIn("pets are not allowed", messages)
        self.assertIn("up to 4 guests", messages)
        self.assertFalse(self.quote(future(5), future(5)).ok)
        self.assertFalse(self.quote(future(-3), future(2)).ok)

    def test_season_minimum_stay(self):
        make_season(self.camping, future(1), future(30), min_nights=5)
        self.assertFalse(self.quote(future(10), future(12), adults=2).ok)
        self.assertTrue(self.quote(future(10), future(15), adults=2).ok)

    def test_opening_period_repeats_every_year(self):
        self.camping.open_all_year = False
        self.camping.opening_date = date(2000, 4, 1)
        self.camping.closing_date = date(2000, 10, 1)
        year = future(0).year + 1
        self.assertTrue(self.quote(date(year, 7, 1), date(year, 7, 5), adults=2).ok)
        self.assertTrue(self.quote(date(year, 9, 28), date(year, 10, 1), adults=2).ok)
        self.assertFalse(self.quote(date(year, 9, 28), date(year, 10, 3), adults=2).ok)
        self.assertFalse(self.quote(date(year, 1, 10), date(year, 1, 12), adults=2).ok)

    def test_opening_period_across_new_year(self):
        self.camping.open_all_year = False
        self.camping.opening_date = date(2000, 11, 1)
        self.camping.closing_date = date(2000, 3, 1)
        self.assertTrue(self.camping.is_open_on(date(2030, 12, 31)))
        self.assertTrue(self.camping.is_open_on(date(2030, 2, 28)))
        self.assertFalse(self.camping.is_open_on(date(2030, 3, 1)))
        self.assertFalse(self.camping.is_open_on(date(2030, 7, 1)))

    def test_deposit(self):
        self.policy.deposit_percent = 25
        self.policy.save()
        self.camping._policy_cache = None
        quote = self.quote(future(10), future(12), adults=2)
        self.assertEqual(quote.deposit, Decimal("10.00"))


class AvailabilityTests(TestCase):
    def setUp(self):
        self.camping = make_camping(open_all_year=True)
        self.acc = make_accommodation(self.camping, units=2)

    def book(self, arrival, departure, status=BookingRequest.Status.CONFIRMED):
        return BookingRequest.objects.create(
            camping=self.camping, accommodation=self.acc, arrival=arrival, departure=departure,
            name="Guest", email="guest@example.com", status=status,
        )

    def test_counts_the_busiest_night_only(self):
        self.book(future(10), future(12))
        self.book(future(12), future(14))  # does not overlap with the first one
        self.assertEqual(available_units(self.acc, future(10), future(14)), 1)
        self.book(future(11), future(13))
        self.assertEqual(available_units(self.acc, future(10), future(14)), 0)

    def test_pending_bookings_do_not_block(self):
        self.book(future(10), future(12), status=BookingRequest.Status.PENDING)
        self.book(future(10), future(12), status=BookingRequest.Status.DECLINED)
        self.assertEqual(available_units(self.acc, future(10), future(12)), 2)

    def test_fully_booked_quote_error(self):
        self.book(future(10), future(12))
        self.book(future(10), future(12))
        with translation.override("en"):
            quote = build_quote(self.camping, self.acc, future(10), future(11), adults=2)
        self.assertIn("fully booked", " ".join(quote.errors))
