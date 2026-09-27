"""Price quotes and availability for booking requests.

A quote adds up, night by night, the price of the accommodation for the
season each night falls into, plus the services that apply: the mandatory
ones (people, tourist tax...) and the optional extras chosen by the guest.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from core.formatting import format_money
from core.i18n import translate_value

from . import catalog

CENT = Decimal("0.01")


def nights_between(arrival, departure):
    for offset in range((departure - arrival).days):
        yield arrival + timedelta(days=offset)


class SeasonCalendar:
    """Which season applies on each night.

    Seasons can have several periods; where a special period (Easter, a long
    weekend...) overlaps a regular season, the special period wins. Nights
    outside every period use the base prices (``None``).
    """

    def __init__(self, seasons):
        self.special, self.regular = [], []
        for season in seasons:
            layer = self.special if season.is_special else self.regular
            layer.extend((period.start_date, period.end_date, season) for period in season.periods.all())

    def season_for(self, day):
        for layer in (self.special, self.regular):
            for start, end, season in layer:
                if start <= day <= end:
                    return season
        return None

    @classmethod
    def for_camping(cls, camping):
        return cls(camping.seasons.prefetch_related("periods"))


def nights_label(n):
    return ngettext("%(count)s night", "%(count)s nights", n) % {"count": n}


def people_label(n):
    return ngettext("%(count)s person", "%(count)s people", n) % {"count": n}


def units_label(n):
    return ngettext("%(count)s unit", "%(count)s units", n) % {"count": n}


@dataclass
class QuoteLine:
    label: str
    detail: str
    amount: Decimal
    kind: str = "service"


@dataclass
class Quote:
    currency: str = "EUR"
    nights: int = 0
    lines: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    total: Decimal = Decimal("0")
    deposit: Decimal | None = None

    @property
    def ok(self):
        return not self.errors

    def as_dict(self):
        return {
            "ok": self.ok,
            "currency": self.currency,
            "nights": self.nights,
            "nights_label": nights_label(self.nights) if self.nights else "",
            "lines": [
                {
                    "label": line.label,
                    "detail": line.detail,
                    "kind": line.kind,
                    "amount": str(line.amount),
                    "amount_display": format_money(line.amount, self.currency),
                }
                for line in self.lines
            ],
            "errors": [str(error) for error in self.errors],
            "total": str(self.total),
            "total_display": format_money(self.total, self.currency),
            "deposit": str(self.deposit) if self.deposit is not None else None,
            "deposit_display": format_money(self.deposit, self.currency) if self.deposit is not None else "",
        }


def minimum_nights(camping, accommodation, arrival, calendar):
    values = [camping.get_policy().min_nights or 1]
    if accommodation is not None and accommodation.min_nights:
        values.append(accommodation.min_nights)
    season = calendar.season_for(arrival) if arrival else None
    if season is not None and season.min_nights:
        values.append(season.min_nights)
    return max(values)


def occupied_units(accommodation, arrival, departure, exclude_pk=None):
    """Highest number of units taken by confirmed stays on any night."""
    from bookings.models import BookingRequest

    bookings = BookingRequest.objects.filter(
        accommodation=accommodation,
        status=BookingRequest.Status.CONFIRMED,
        arrival__lt=departure,
        departure__gt=arrival,
    )
    if exclude_pk:
        bookings = bookings.exclude(pk=exclude_pk)
    ranges = list(bookings.values_list("arrival", "departure", "units"))
    peak = 0
    for night in nights_between(arrival, departure):
        peak = max(peak, sum(units for start, end, units in ranges if start <= night < end))
    return peak


def available_units(accommodation, arrival, departure, exclude_pk=None):
    return max(accommodation.units - occupied_units(accommodation, arrival, departure, exclude_pk), 0)


def _group_nights(nights, price_of):
    """[(price, season, count), ...] merging consecutive nights with equal price."""
    groups = []
    for night in nights:
        price, season = price_of(night)
        if groups and groups[-1][0] == price and groups[-1][1] == season:
            groups[-1][2] += 1
        else:
            groups.append([price, season, 1])
    return groups


def _quantity_label(unit, adults, children, pets):
    if unit == "adult_night":
        return ngettext("%(count)s adult", "%(count)s adults", adults) % {"count": adults}
    if unit == "child_night":
        return ngettext("%(count)s child", "%(count)s children", children) % {"count": children}
    if unit in ("person_night", "person_stay"):
        return people_label(adults + children)
    if unit == "pet_night":
        return ngettext("%(count)s pet", "%(count)s pets", pets) % {"count": pets}
    return ""


def _service_factor(unit, adults, children, pets):
    persons = adults + children
    return {
        "night": 1,
        "stay": 1,
        "adult_night": adults,
        "child_night": children,
        "person_night": persons,
        "person_stay": persons,
        "pet_night": pets,
    }.get(unit, 1)


def build_quote(
    camping,
    accommodation,
    arrival,
    departure,
    adults=2,
    children=0,
    pets=0,
    extras=(),
    check_availability=True,
    exclude_booking_pk=None,
    allow_past=False,
    units=1,
    allow_inactive=False,
):
    """Validate a stay and compute its estimated price.

    ``units`` is the number of accommodation units booked (e.g. two pitches);
    the accommodation price and its capacity are multiplied by it.
    ``allow_inactive`` lets the panel price accommodation types hidden from
    the website.
    """
    quote = Quote(currency=camping.currency)
    policy = camping.get_policy()
    calendar = SeasonCalendar.for_camping(camping)
    errors = quote.errors
    adults, children, pets = int(adults or 0), int(children or 0), int(pets or 0)
    units = max(int(units or 1), 1)

    valid_accommodation = (
        accommodation is not None
        and accommodation.camping_id == camping.pk
        and (accommodation.is_active or allow_inactive)
    )
    if not valid_accommodation:
        errors.append(_("Please choose an accommodation."))
    if not arrival or not departure:
        errors.append(_("Please choose your arrival and departure dates."))
        return quote
    if departure <= arrival:
        errors.append(_("The departure date must be after the arrival date."))
        return quote
    if not allow_past and arrival < timezone.localdate():
        errors.append(_("The arrival date cannot be in the past."))

    nights = (departure - arrival).days
    quote.nights = nights

    if not all(camping.is_open_on(night) for night in nights_between(arrival, departure)):
        errors.append(
            _("The camping is open from %(start)s to %(end)s.")
            % {
                "start": date_format(camping.opening_date, "MONTH_DAY_FORMAT"),
                "end": date_format(camping.closing_date, "MONTH_DAY_FORMAT"),
            }
        )

    min_nights = minimum_nights(camping, accommodation if valid_accommodation else None, arrival, calendar)
    if nights < min_nights:
        errors.append(_("The minimum stay for these dates is %(nights)s.") % {"nights": nights_label(min_nights)})
    if policy.max_nights and nights > policy.max_nights:
        errors.append(_("The maximum stay is %(nights)s.") % {"nights": nights_label(policy.max_nights)})

    if adults < 1:
        errors.append(_("At least one adult is required."))
    if pets and not policy.pets_allowed:
        errors.append(_("Sorry, pets are not allowed."))

    if not valid_accommodation:
        return quote

    capacity = accommodation.max_guests * units
    if adults + children > capacity:
        errors.append(
            ngettext(
                "This accommodation is for up to %(count)s guest.",
                "This accommodation is for up to %(count)s guests.",
                capacity,
            )
            % {"count": capacity}
        )

    if check_availability and not errors:
        if available_units(accommodation, arrival, departure, exclude_booking_pk) < units:
            errors.append(_("Sorry, this accommodation is fully booked for these dates."))

    stay_nights = list(nights_between(arrival, departure))
    persons = adults + children
    total = Decimal("0")

    # Accommodation
    acc_rates = accommodation.rate_map()
    groups = _group_nights(
        stay_nights,
        lambda night: (accommodation.price_for(calendar.season_for(night), acc_rates), calendar.season_for(night)),
    )
    name = accommodation.display_name
    for price, season, count in groups:
        if accommodation.price_unit == "person_night":
            amount = price * count * persons
            detail = f"{nights_label(count)} × {people_label(persons)} × {format_money(price, camping.currency)}"
        else:
            amount = price * count * units
            detail = f"{nights_label(count)} × {format_money(price, camping.currency)}"
            if units > 1:
                detail = f"{units_label(units)} × {detail}"
        if season is not None and len(groups) > 1:
            detail = f"{detail} · {translate_value(season.name)}"
        quote.lines.append(QuoteLine(name, detail, amount.quantize(CENT, ROUND_HALF_UP), "accommodation"))
        total += amount

    # Services: mandatory ones plus the optional extras requested.
    extra_ids = {service.pk for service in extras}
    services = camping.services.filter(is_active=True).prefetch_related("rates", "accommodations")
    for service in services:
        if service.mode == "included" or not service.applies_to(accommodation):
            continue
        if service.mode == "optional" and service.pk not in extra_ids:
            continue
        factor = _service_factor(service.unit, adults, children, pets)
        if factor <= 0:
            continue
        rates = service.rate_map()
        if service.unit in catalog.PER_NIGHT_UNITS:
            amounts = [service.price_for(calendar.season_for(night), rates) for night in stay_nights]
            amount = sum(amounts, Decimal("0")) * factor
            parts = [
                label
                for label in (_quantity_label(service.unit, adults, children, pets), nights_label(nights))
                if label
            ]
            if len(set(amounts)) == 1:
                parts.append(format_money(amounts[0], camping.currency))
            detail = " × ".join(parts)
        else:
            price = service.price_for(calendar.season_for(arrival), rates)
            amount = price * factor
            quantity = _quantity_label(service.unit, adults, children, pets)
            price_text = format_money(price, camping.currency)
            detail = f"{quantity} × {price_text}" if quantity else price_text
        if amount <= 0:
            continue
        quote.lines.append(QuoteLine(service.display_name, detail, amount.quantize(CENT, ROUND_HALF_UP)))
        total += amount

    quote.total = total.quantize(CENT, ROUND_HALF_UP)
    if policy.deposit_percent:
        quote.deposit = (quote.total * policy.deposit_percent / 100).quantize(CENT, ROUND_HALF_UP)
    return quote
