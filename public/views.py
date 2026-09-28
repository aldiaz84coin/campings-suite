import logging

from django.core.cache import cache
from django.db.models import Prefetch
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone, translation
from django.utils.text import Truncator
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from bookings.emails import send_new_booking_emails
from bookings.forms import BookingRequestForm, QuoteForm, StaySearchForm
from bookings.models import BookingRequest
from campings import catalog
from campings.models import Camping, Photo
from campings.seasons import has_uncovered_days
from core.urlutils import camping_reverse, camping_site_url, request_camping_id

logger = logging.getLogger(__name__)

BOOKING_RATE_LIMIT = 6  # requests per IP and hour


def public_campings():
    return Camping.objects.filter(is_published=True, is_approved=True)


def can_preview(user, camping):
    return user.is_authenticated and (user.is_superuser or camping.memberships.filter(user_id=user.pk).exists())


def get_camping(request, slug=None):
    """Camping for this request: by its own host or slug, public or preview."""
    if request_camping_id(request):
        camping = get_object_or_404(Camping, pk=request.domain_camping_id)
    else:
        camping = get_object_or_404(Camping, slug=slug)
    if not camping.is_public and not can_preview(request.user, camping):
        raise Http404("Camping not found")
    return camping


def canonical_redirect(request, camping):
    """301 from the platform address to the camping's own website, if it has one."""
    if request_camping_id(request) or request.method not in ("GET", "HEAD"):
        return None
    if not camping.is_public or not camping.site_url:
        return None
    match = request.resolver_match
    kwargs = {key: value for key, value in match.kwargs.items() if key != "slug"}
    url = camping_site_url(camping, match.view_name, **kwargs)
    query = request.META.get("QUERY_STRING", "")
    return HttpResponsePermanentRedirect(f"{url}?{query}" if query else url)


def client_ip(request):
    return (
        request.META.get("HTTP_FLY_CLIENT_IP")
        or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )


def absolute(request, url):
    return request.build_absolute_uri(url) if url and not url.startswith("http") else url


def home(request):
    """Root of the platform host: there is no public directory, only the panel.

    On a camping's own host the root is its website (see ``urls_domain``).
    """
    return redirect("panel:home")


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
        data["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": float(camping.latitude),
            "longitude": float(camping.longitude),
        }
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


def coming_soon(request):
    """Home of a camping's own host while its website is not public."""
    camping = get_object_or_404(Camping, pk=request.domain_camping_id)
    return render(request, "public/coming_soon.html", {"camping": camping, "noindex": True})


def camping_detail(request, slug=None):
    if request_camping_id(request):
        camping = get_object_or_404(Camping, pk=request.domain_camping_id)
        if not camping.is_public and not can_preview(request.user, camping):
            return coming_soon(request)
    else:
        camping = get_camping(request, slug)
        if response := canonical_redirect(request, camping):
            return response
    today = timezone.localdate()

    photos = list(camping.photos.all())
    accommodations = list(
        camping.accommodations.filter(is_active=True).prefetch_related(
            "rates", Prefetch("photos", queryset=Photo.objects.order_by("position", "id"))
        )
    )
    all_seasons = list(camping.seasons.prefetch_related("periods"))
    seasons = []
    for season in all_seasons:
        season.upcoming = season.upcoming_periods(today)
        if season.upcoming:
            seasons.append(season)
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
        "show_base_prices": bool(seasons) and has_uncovered_days(camping, all_seasons, today),
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
    if response := canonical_redirect(request, camping):
        return response
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
                return redirect(camping_reverse(request, "public:booking_done", camping, token=booking_request.token))
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
    if response := canonical_redirect(request, camping):
        return response
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
    camping = None
    if slug or request_camping_id(request):
        camping = get_camping(request, slug)
        if response := canonical_redirect(request, camping):
            return response
    return render(request, "public/privacy.html", {"camping": camping})


def _legal_page(request, slug, template):
    camping = get_camping(request, slug)
    if response := canonical_redirect(request, camping):
        return response
    return render(request, template, {"camping": camping})


def legal_notice(request, slug=None):
    return _legal_page(request, slug, "public/legal_notice.html")


def cookies_policy(request, slug=None):
    return _legal_page(request, slug, "public/cookies.html")


# --- SEO -----------------------------------------------------------------------


@require_GET
def robots_txt(request):
    sitemap = request.build_absolute_uri("/sitemap.xml")
    if request_camping_id(request):
        rules = ["Disallow: /*/panel/", "Disallow: /*/book/"]
    else:
        rules = ["Disallow: /*/panel/", "Disallow: /superadmin/", "Disallow: /*/camping/*/book/"]
    lines = ["User-agent: *", *rules, f"Sitemap: {sitemap}", ""]
    return HttpResponse("\n".join(lines), content_type="text/plain")


@require_GET
def sitemap_xml(request):
    """Pages served on this host.

    A camping's own host lists its pages; the platform host only lists the
    public campings that do not have an address of their own yet.
    """
    if request_camping_id(request):
        campings = public_campings().filter(pk=request.domain_camping_id)
    else:
        campings = [camping for camping in public_campings().order_by("pk") if not camping.site_url]

    entries = []
    for camping in campings:
        alternates = _alternates(request, camping)
        entries.extend(
            {"loc": url, "alternates": alternates, "lastmod": camping.updated_at}
            for code, url in alternates
            if code != "x-default"
        )
    return render(request, "public/sitemap.xml", {"entries": entries}, content_type="application/xml")
