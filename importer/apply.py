"""Turn a reviewed import into the camping's data."""

import logging
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.db.models import Max
from django.utils import timezone, translation

from campings import catalog
from campings.models import (
    AccommodationRate,
    AccommodationType,
    Camping,
    Facility,
    Photo,
    Season,
    SeasonPeriod,
    Service,
    ServiceRate,
)
from campings.seasons import overlapping_season
from core.images import ImageProcessingError, process_logo, process_photo

from .fetch import FetchError, fetch

logger = logging.getLogger(__name__)

TEXT_FIELDS = {
    "name": 150,
    "phone": 40,
    "whatsapp": 40,
    "address": 255,
    "postal_code": 20,
    "city": 100,
    "region": 100,
    "country": 100,
    "legal_name": 200,
    "tax_id": 30,
    "registry_info": 300,
    "tourism_registration": 60,
}
CODE_FIELDS = ("ga_measurement_id", "search_console_verification")
URL_FIELDS = ("instagram", "facebook")
SERVICE_ICON_KEYS = {key for key, _label in catalog.SERVICE_ICONS}
SERVICE_UNIT_KEYS = {key for key, _label in catalog.SERVICE_UNITS}
SERVICE_MODE_KEYS = {key for key, _label in catalog.SERVICE_MODES}
ACCOMMODATION_KIND_KEYS = {key for key, _label, _icon in catalog.ACCOMMODATION_KINDS}
IMAGE_ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8"


def _decimal(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _time(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


def _apply_fields(camping, data, chosen):
    fields = data.get("fields", {})
    policy = camping.get_policy()
    policy_changed = False
    composite = {
        "location": fields.get("latitude"),
        "opening": fields.get("open_all_year") or fields.get("opening_date"),
    }
    for key in chosen:
        value = composite[key] if key in composite else fields.get(key)
        if value in (None, ""):
            continue
        if key in TEXT_FIELDS:
            setattr(camping, key, str(value)[: TEXT_FIELDS[key]])
        elif key == "email":
            try:
                validate_email(value)
            except ValidationError:
                continue
            camping.email = value
        elif key in CODE_FIELDS:
            try:
                Camping._meta.get_field(key).run_validators(value)
            except ValidationError:
                continue
            setattr(camping, key, value)
        elif key in URL_FIELDS:
            try:
                URLValidator()(value)
            except ValidationError:
                continue
            setattr(camping, key, value[:200])
        elif key == "location":
            lat, lng = _decimal(fields.get("latitude")), _decimal(fields.get("longitude"))
            if lat is not None and lng is not None:
                camping.latitude = Decimal(str(fields["latitude"])).quantize(Decimal("0.000001"))
                camping.longitude = Decimal(str(fields["longitude"])).quantize(Decimal("0.000001"))
        elif key == "stars" and str(value).isdigit() and 1 <= int(value) <= 5:
            camping.stars = int(value)
        elif key == "opening":
            if fields.get("open_all_year"):
                camping.open_all_year = True
            else:
                opening, closing = _date(fields.get("opening_date")), _date(fields.get("closing_date"))
                if opening and closing:
                    camping.open_all_year = False
                    camping.opening_date, camping.closing_date = opening, closing
        elif key in ("check_in_from", "check_out_until") and _time(value):
            setattr(policy, key, _time(value))
            policy_changed = True
    if policy_changed:
        policy.save()


def _apply_texts(camping, data, chosen, location_info):
    languages = list(camping.languages or [])
    platform = {code for code, _name in settings.LANGUAGES}
    for choice in chosen:
        code, _sep, part = choice.partition(":")
        value = (data.get("texts", {}).get(code) or {}).get(part)
        if not value or code not in platform or part not in ("tagline", "description"):
            continue
        field_value = dict(getattr(camping, part) or {})
        field_value[code] = value[:180] if part == "tagline" else value
        setattr(camping, part, field_value)
        if code not in languages:
            languages.append(code)
    if location_info:
        info = dict(camping.location_info or {})
        info.update({code: text for code, text in data.get("location_info", {}).items() if code in platform})
        camping.location_info = info
    camping.languages = languages


def _apply_facilities(camping, keys):
    created = 0
    for key in keys:
        if key in catalog.FACILITY_MAP:
            _facility, was_created = Facility.objects.get_or_create(camping=camping, kind=key)
            created += was_created
    return created


def _apply_seasons(camping, data, chosen, kinds):
    created, skipped_periods = {}, 0
    for season in data.get("seasons", []):
        key = season["key"]
        if key not in chosen:
            continue
        kind = kinds.get(key) if kinds.get(key) in Season.Kind.values else (season.get("kind") or Season.Kind.MID)
        name = (season.get("name") or "").strip()
        if not name:
            with translation.override(camping.default_language):
                name = str(Season.Kind(kind).label)
        obj = Season.objects.create(
            camping=camping,
            name={camping.default_language: name[:60]},
            kind=kind,
            color=Season.KIND_COLORS.get(kind, Season.KIND_COLORS["mid"]),
        )
        own = []
        for start_raw, end_raw in season.get("periods", []):
            start, end = _date(start_raw), _date(end_raw)
            if not start or not end or end < start:
                continue
            clash = any(start <= other_end and other_start <= end for other_start, other_end in own)
            if clash or overlapping_season(camping, obj.is_special, start, end, exclude_season=obj):
                skipped_periods += 1
                continue
            SeasonPeriod.objects.create(season=obj, start_date=start, end_date=end)
            own.append((start, end))
        created[key] = obj
    return created, skipped_periods


def _apply_items(camping, data, chosen, types, modes, seasons):
    language = camping.default_language
    accommodations = services = 0
    next_acc = (camping.accommodations.aggregate(top=Max("position"))["top"] or 0) + 1
    next_service = (camping.services.aggregate(top=Max("position"))["top"] or 0) + 1
    for item in data.get("items", []):
        key = item["key"]
        if key not in chosen:
            continue
        kind, _sep, detail = (types.get(key) or "").partition(":")
        if kind not in ("acc", "svc"):
            kind = "acc" if item.get("kind") == "accommodation" else "svc"
            detail = item.get("accommodation_kind") if kind == "acc" else item.get("unit")
        base = _decimal(item.get("base")) or Decimal("0")
        rates = {
            seasons[season_key]: price
            for season_key, value in (item.get("prices") or {}).items()
            if season_key in seasons and (price := _decimal(value)) is not None
        }
        name = {language: item["label"][:120]}
        if kind == "acc":
            accommodation = AccommodationType.objects.create(
                camping=camping,
                kind=detail if detail in ACCOMMODATION_KIND_KEYS else "other",
                name=name,
                max_guests=min(max(int(item.get("max_guests") or 4), 1), 50),
                units=1,
                base_price=base,
                position=next_acc,
            )
            next_acc += 1
            AccommodationRate.objects.bulk_create(
                AccommodationRate(accommodation=accommodation, season=season, price=price)
                for season, price in rates.items()
            )
            accommodations += 1
        else:
            unit = detail if detail in SERVICE_UNIT_KEYS else "night"
            mode = modes.get(key) if modes.get(key) in SERVICE_MODE_KEYS else (item.get("mode") or "optional")
            service = Service.objects.create(
                camping=camping,
                name=name,
                icon=item.get("icon") if item.get("icon") in SERVICE_ICON_KEYS else "tag",
                price=base,
                unit=unit,
                mode=mode if mode in SERVICE_MODE_KEYS else "optional",
                position=next_service,
            )
            next_service += 1
            ServiceRate.objects.bulk_create(
                ServiceRate(service=service, season=season, price=price) for season, price in rates.items()
            )
            services += 1
    return accommodations, services


def apply_import(site_import, choices):
    """Create or update the camping's data with what the user ticked.

    ``choices`` keys: fields, texts, location_info, facilities, seasons,
    season_kinds, items, item_types, item_modes, photos, logo.
    """
    camping = site_import.camping
    data = site_import.data
    with transaction.atomic():
        _apply_fields(camping, data, choices.get("fields", []))
        _apply_texts(camping, data, choices.get("texts", []), choices.get("location_info"))
        camping.save()
        facilities = _apply_facilities(camping, choices.get("facilities", []))
        seasons, skipped_periods = _apply_seasons(
            camping, data, set(choices.get("seasons", [])), choices.get("season_kinds", {})
        )
        accommodations, services = _apply_items(
            camping,
            data,
            set(choices.get("items", [])),
            choices.get("item_types", {}),
            choices.get("item_modes", {}),
            seasons,
        )
        queue = []
        if choices.get("logo") and data.get("logo"):
            queue.append({"url": data["logo"], "logo": True})
        photos = data.get("photos", [])
        for index in choices.get("photos", []):
            if 0 <= index < len(photos):
                photo = photos[index]
                queue.append(
                    {
                        "url": photo["url"],
                        "original": photo.get("original") or photo["url"],
                        "alt": photo.get("alt") or "",
                        "lang": photo.get("lang") or data.get("language"),
                    }
                )
        site_import.photo_queue = queue
        site_import.photos_done = site_import.photos_failed = 0
        site_import.status = site_import.Status.APPLIED
        site_import.applied_at = timezone.now()
        site_import.save()
    return {
        "facilities": facilities,
        "seasons": len(seasons),
        "skipped_periods": skipped_periods,
        "accommodations": accommodations,
        "services": services,
        "photos": len(queue),
    }


def _download(entry):
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    urls = [entry.get("original"), entry["url"]] if entry.get("original") != entry["url"] else [entry["url"]]
    last_error = None
    for url in filter(None, urls):
        try:
            fetched = fetch(url, max_bytes=max_bytes, accept=IMAGE_ACCEPT, timeout=15)
        except FetchError as error:
            last_error = error
            continue
        if (
            fetched.content_type.startswith("image/")
            or fetched.content[:4] in (b"\x89PNG", b"RIFF")
            or fetched.content[:3] == b"\xff\xd8\xff"
        ):
            return fetched.content
        last_error = FetchError("not an image")
    raise last_error or FetchError("not an image")


def process_photo_queue(site_import, seconds=8):
    """Download and save queued photos until the time runs out; returns what is left."""
    camping = site_import.camping
    queue = list(site_import.photo_queue or [])
    deadline = time.monotonic() + seconds
    position = (camping.photos.aggregate(top=Max("position"))["top"] or 0) + 1
    while queue and time.monotonic() < deadline:
        entry = queue.pop(0)
        try:
            if not entry.get("logo") and camping.photos.count() >= settings.MAX_PHOTOS_PER_CAMPING:
                raise ImageProcessingError("photo limit")
            content = _download(entry)
            if entry.get("logo"):
                processed = process_logo(BytesIO(content))
                camping.logo.save(processed.file.name, processed.file, save=False)
                camping.save()
            else:
                large, thumb = process_photo(BytesIO(content))
                caption = {entry["lang"]: entry["alt"][:200]} if entry.get("alt") and entry.get("lang") else {}
                photo = Photo(
                    camping=camping, position=position, width=large.width, height=large.height, caption=caption
                )
                photo.image.save(large.file.name, large.file, save=False)
                photo.thumbnail.save(thumb.file.name.replace(".webp", "-thumb.webp"), thumb.file, save=False)
                photo.save()
                position += 1
            site_import.photos_done += 1
        except (FetchError, ImageProcessingError) as error:
            logger.info("Could not import %s: %s", entry.get("url"), error)
            site_import.photos_failed += 1
        site_import.photo_queue = queue
        site_import.save(update_fields=["photo_queue", "photos_done", "photos_failed"])
    return len(queue)
