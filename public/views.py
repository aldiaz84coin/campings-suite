import logging

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.text import Truncator
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from bookings.emails import send_new_booking_emails
from bookings.forms import BookingRequestForm, QuoteForm, StaySearchForm
from bookings.models import BookingRequest
from campings import catalog
from campings.models import AccommodationType, Camping, Photo
from core.urlutils import camping_reverse

logger = logging.getLogger(__name__)

HOME_FACILITY_FILTERS = ["pool", "beach", "pets", "wifi", "restaurant", "playground", "mountain", "motorhome_service"]
BOOKING_RATE_LIMIT = 6  # requests per IP and hour


def public_campings():
    return Camping.objects.filter(is_published=True, is_approved=True)


def can_preview(user, camping):
    return user.is_authenticated and (
        user.is_superuser or camping.memberships.filter(user_id=user.pk).exists()
    )


def get_camping(request, slug=None):
    """Camping for this request: by custom domain or slug, public or preview."""
    if getattr(request, "domain_camping_id", None):
        camping = get_object_or_404(Camping, pk=request.domain_camping_id)
    else:
        camping = get_object_or_404(Camping, slug=slug)
    if not camping.is_public and not can_preview(request.user, camping):
        raise Http404("Camping not found")
    return camping


def client_ip(request):
    return (
        request.META.get("HTTP_FLY_CLIENT_IP")
        or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )


def absolute(request, url):
    return request.build_absolute_uri(url) if url and not url.startswith("http") else url


# --- Directory -----------------------------------------------------------------


def home(request):
    q = request.GET.get("q", "").strip()
    region = request.GET.get("region", "").strip()
    facility = request.GET.get("facility", "").strip()

    campings = public_campings()
    if q:
        campings = campings.filter(
            Q(name__icontains=q) | Q(city__icontains=q) | Q(region__icontains=q) | Q(country__icontains=q)
        )
    if region:
        campings = campings.filter(region__iexact=region)
    if facility in catalog.FACILITY_MAP:
        campings = campings.filter(facilities__kind=facility).distinct()
    campings = campings.prefetch_related(
        Prefetch("photos", queryset=Photo.objects.order_by("position", "id")),
        "facilities",
        Prefetch("accommodations", queryset=AccommodationType.objects.filter(is_active=True).prefetch_related("rates")),
    ).order_by("name")

    page = Paginator(campings, 12).get_page(request.GET.get("page"))
    regions = (
        public_campings().exclude(region="").order_by("region").values_list("region", flat=True).distinct()
    )
    facility_filters = [(key, catalog.FACILITY_MAP[key]) for key in HOME_FACILITY_FILTERS]
    alternates = []
    for code, _name in settings.LANGUAGES:
        with translation.override(code):
            alternates.append((code, absolute(request, reverse("public:home"))))
    with translation.override(settings.LANGUAGE_CODE):
        alternates.append(("x-default", absolute(request, reverse("public:home"))))
    return render(
        request,
        "public/home.html",
        {
            "page": page,
            "campings": page.object_list,
            "total": page.paginator.count,
            "q": q,
            "region": region,
            "facility": facility,
            "regions": regions,
            "facility_filters": facility_filters,
            "is_filtered": bool(q or region or facility),
            "alternates": alternates,
            "canonical": dict(alternates).get(get_language()),
            "noindex": bool(q or region or facility or page.number > 1),
        },
    )


# --- Camping page --------------------------------------------------------------


def _facility_groups(facilities):
    labels = dict(catalog.FACILITY_GROUPS)
    grouped = {}
    for facility in facilities:
        grouped.setdefault(facility.group, []).append(facility)
    ordered = [(key, labels[key], grouped[key]) for key, _label in catalog.FACILITY_GROUPS if key in grouped]
    if "other" in grouped:
        ordered.append(("other", _("Other"), grouped["other"]))
    return ordered


def _price_rows(items, seasons, kind_of):
    rows = []
    for item in items:
        rates = item.rate_map()
        rows.append(
            {
                "name": item.display_name,
                "icon": kind_of(item)["icon"],
                "unit": kind_of(item)["unit"],
                "kind": kind_of(item)["kind"],
                "prices": [item.price_for(season, rates) for season in seasons],
                "base": item.price_for(None),
            }
        )
    return rows


def _json_ld(request, camping, photos, facilities, starting_price):
    data = {
        "@context": "https://schema.org",
        "@type": "Campground",
        "name": camping.name,
        "url": request.build_absolute_uri(),
        "description": Truncator(camping.t("description") or camping.t("tagline")).chars(300),
    }
    if photos:
        data["image"] = [absolute(request, photo.image.url) for photo in photos[:6]]
    if camping.address or camping.city:
        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": camping.address,
            "postalCode": camping.postal_code,
            "addressLocality": camping.city,
            "addressRegion": camping.region,
            "addressCountry": camping.country,
        }
    if camping.latitude is not None and camping.longitude is not None:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": float(camping.latitude), "longitude": float(camping.longitude)}
    if camping.phone:
        data["telephone"] = camping.phone
    if camping.email:
        data["email"] = camping.email
    if facilities:
        data["amenityFeature"] = [
            {"@type": "LocationFeatureSpecification", "name": str(f.display_name), "value": True} for f in facilities
        ]
    if starting_price:
        data["priceRange"] = f"{starting_price}+ {camping.currency}"
    if camping.stars:
        data["starRating"] = {"@type": "Rating", "ratingValue": camping.stars}
    return data


def _alternates(request, camping, name="public:camping_detail", **kwargs):
    links = []
    for code in camping.content_languages:
        with translation.override(code):
            links.append((code, absolute(request, camping_reverse(request, name, camping, **kwargs))))
    if links:
        with translation.override(camping.default_language):
            links.append(("x-default", absolute(request, camping_reverse(request, name, camping, **kwargs))))
    return links


def camping_detail(request, slug=None):
    camping = get_camping(request, slug)
    today = timezone.localdate()

    photos = list(camping.photos.all())
    accommodations = list(
        camping.accommodations.filter(is_active=True).prefetch_related(
            "rates", Prefetch("photos", queryset=Photo.objects.order_by("position", "id"))
        )
    )
    seasons = [season for season in camping.seasons.all() if season.end_date >= today]
    services = list(camping.services.filter(is_active=True).prefetch_related("rates", "accommodations"))
    facilities = list(camping.facilities.all())
    policy = camping.get_policy()

    prices = [a.lowest_price() for a in accommodations]
    prices = [p for p in prices if p]
    starting_price = min(prices) if prices else None
    current_language = get_language()
    translated = current_language in camping.content_languages
    alternates = _alternates(request, camping)
    canonical = dict(alternates).get(current_language if translated else camping.default_language)

    accommodation_rows = _price_rows(
        accommodations,
        seasons,
        lambda a: {"icon": a.kind_icon, "unit": a.get_price_unit_display(), "kind": "accommodation"},
    )
    service_rows = _price_rows(
        [s for s in services if s.mode != "included"],
        seasons,
        lambda s: {"icon": s.icon, "unit": s.get_unit_display(), "kind": s.mode},
    )
    season_minimums = [s for s in seasons if s.min_nights and s.min_nights > policy.min_nights]

    context = {
        "camping": camping,
        "photos": photos,
        "cover": photos[0] if photos else None,
        "accommodations": accommodations,
        "facility_groups": _facility_groups(facilities),
        "facility_count": len(facilities),
        "seasons": seasons,
        "accommodation_rows": accommodation_rows,
        "service_rows": service_rows,
        "included_services": [s for s in services if s.mode == "included"],
        "policy": policy,
        "season_minimums": season_minimums,
        "starting_price": starting_price,
        "search_form": StaySearchForm(camping),
        "is_preview": not camping.is_public,
        "alternates": alternates,
        "canonical": canonical,
        "noindex": not camping.is_public or not translated,
        "json_ld": _json_ld(request, camping, photos, facilities, starting_price),
        "meta_description": Truncator(camping.t("tagline") or camping.t("description")).chars(160),
        "og_image": absolute(request, photos[0].image.url) if photos else "",
        "translation_missing": not translated,
        "map": camping.map_links(),
    }
    return render(request, "public/camping_detail.html", context)


# --- Booking -------------------------------------------------------------------


def _booking_initial(request, camping):
    initial = {}
    for key in ("arrival", "departure", "adults", "children", "pets"):
        if request.GET.get(key):
            initial[key] = request.GET[key]
    accommodation_id = request.GET.get("accommodation")
    if accommodation_id and accommodation_id.isdigit():
        initial["accommodation"] = int(accommodation_id)
    return initial


def _rate_limited(request, camping):
    key = f"booking-rate:{camping.pk}:{client_ip(request)}"
    count = cache.get(key, 0)
    if count >= BOOKING_RATE_LIMIT:
        return True
    cache.set(key, count + 1, 3600)
    return False


def booking(request, slug=None):
    camping = get_camping(request, slug)
    accommodations = list(
        camping.accommodations.filter(is_active=True).prefetch_related(
            "rates", Prefetch("photos", queryset=Photo.objects.order_by("position", "id"))
        )
    )
    quote = None

    if request.method == "POST" and camping.accepts_booking_requests:
        form = BookingRequestForm(camping, request.POST)
        if form.is_valid():
            if form.is_spam:
                logger.info("Ignored spam booking request for %s", camping.slug)
                return redirect(camping_reverse(request, "public:camping_detail", camping))
            if _rate_limited(request, camping):
                form.add_error(None, _("Too many requests from your connection. Please try again later."))
            else:
                booking_request = form.save()
                send_new_booking_emails(request, booking_request)
                return redirect(
                    camping_reverse(request, "public:booking_done", camping, token=booking_request.token)
                )
        quote = form.quote
    else:
        initial = _booking_initial(request, camping)
        form = BookingRequestForm(camping, initial=initial)
        if {"accommodation", "arrival", "departure"} <= initial.keys():
            quote_form = QuoteForm(camping, {**initial, "extras": []})
            if quote_form.is_valid():
                quote = quote_form.quote()

    return render(
        request,
        "public/booking.html",
        {
            "camping": camping,
            "form": form,
            "quote": quote.as_dict() if quote else None,
            "accommodations": accommodations,
            "policy": camping.get_policy(),
            "services": camping.services.filter(is_active=True).prefetch_related("accommodations"),
            "is_preview": not camping.is_public,
            "noindex": True,
            "quote_url": camping_reverse(request, "public:quote", camping),
            "selected_extras": [str(value) for value in (form["extras"].value() or [])],
        },
    )


def booking_done(request, token, slug=None):
    camping = get_camping(request, slug)
    booking_request = get_object_or_404(BookingRequest, token=token, camping=camping)
    return render(
        request,
        "public/booking_done.html",
        {
            "camping": camping,
            "booking": booking_request,
            "quote": booking_request.guest_quote,
            "accommodation_name": booking_request.accommodation_label(booking_request.language),
            "policy": camping.get_policy(),
            "noindex": True,
        },
    )


@require_GET
def quote(request, slug=None):
    camping = get_camping(request, slug)
    form = QuoteForm(camping, request.GET)
    if not form.is_valid():
        errors = [str(e) for field_errors in form.errors.values() for e in field_errors]
        return JsonResponse({"ok": False, "errors": errors, "lines": [], "total_display": ""})
    return JsonResponse(form.quote().as_dict())


def privacy(request, slug=None):
    camping = get_camping(request, slug) if (slug or getattr(request, "domain_camping_id", None)) else None
    return render(request, "public/privacy.html", {"camping": camping})


# --- SEO -----------------------------------------------------------------------


@require_GET
def robots_txt(request):
    sitemap = request.build_absolute_uri("/sitemap.xml")
    lines = ["User-agent: *", "Disallow: /*/panel/", "Disallow: /superadmin/", "Disallow: /*/camping/*/book/", f"Sitemap: {sitemap}", ""]
    return HttpResponse("\n".join(lines), content_type="text/plain")


@require_GET
def sitemap_xml(request):
    entries = []
    if getattr(request, "domain_camping_id", None):
        campings = Camping.objects.filter(pk=request.domain_camping_id)
    else:
        campings = public_campings().order_by("pk")
        home_links = []
        for code, _name in settings.LANGUAGES:
            with translation.override(code):
                home_links.append((code, absolute(request, reverse("public:home"))))
        entries.extend({"loc": url, "alternates": home_links, "lastmod": None} for _code, url in home_links)

    for camping in campings:
        alternates = _alternates(request, camping)
        entries.extend(
            {"loc": url, "alternates": alternates, "lastmod": camping.updated_at}
            for code, url in alternates
            if code != "x-default"
        )
    return render(request, "public/sitemap.xml", {"entries": entries}, content_type="application/xml")
