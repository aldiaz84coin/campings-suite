"""Import a camping's details, photos and prices from its current website."""

from datetime import date

from django import forms
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from campings import catalog
from campings.models import BookingPolicy, Camping, Season
from core.i18n import language_name, translate_value
from importer.apply import apply_import, process_photo_queue
from importer.fetch import FetchError
from importer.models import SiteImport
from importer.service import run_import

from ..utils import camping_view, panel_render, wants_json

PRESELECTED_PHOTOS = 12


class ImportForm(forms.Form):
    url = forms.CharField(
        label=gettext_lazy("Address of the current website"),
        max_length=500,
        widget=forms.TextInput(
            attrs={"placeholder": "https://www.mycamping.com", "inputmode": "url", "autocomplete": "url"}
        ),
    )


def start_import(request, camping, url):
    """Read the website; on success returns the review URL, else adds an error message."""
    try:
        site_import = run_import(camping, url, user=request.user)
    except FetchError as error:
        messages.error(request, _("%(url)s could not be read: %(error)s") % {"url": url, "error": error})
        return None
    return redirect("panel:import_review", slug=camping.slug, pk=site_import.pk)


@camping_view(owner_only=True)
def import_start(request, camping):
    form = ImportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        response = start_import(request, camping, form.cleaned_data["url"])
        if response is not None:
            return response
    context = {"form": form, "imports": camping.site_imports.all()[:5]}
    return panel_render(request, "panel/import_start.html", context, section="import")


def _field_label(key):
    labels = {
        "location": _("Map location"),
        "opening": _("Opening period"),
        "check_in_from": _("Check-in from"),
        "check_out_until": _("Check-out until"),
        "stars": _("Category (stars)"),
    }
    if key in labels:
        return labels[key]
    return str(Camping._meta.get_field(key).verbose_name).capitalize()


def _field_rows(camping, fields):
    policy = camping.get_policy()
    rows = []
    for key in (
        "name",
        "email",
        "phone",
        "whatsapp",
        "instagram",
        "facebook",
        "address",
        "postal_code",
        "city",
        "region",
        "country",
        "location",
        "stars",
        "opening",
        "check_in_from",
        "check_out_until",
        "legal_name",
        "tax_id",
        "registry_info",
        "tourism_registration",
        "ga_measurement_id",
        "search_console_verification",
    ):
        checked = False
        if key == "location":
            if fields.get("latitude") is None:
                continue
            value = f"{fields['latitude']}, {fields['longitude']}"
            current = f"{camping.latitude}, {camping.longitude}" if camping.latitude is not None else ""
        elif key == "opening":
            if fields.get("open_all_year"):
                value = _("All year")
            elif fields.get("opening_date"):
                start = date.fromisoformat(fields["opening_date"])
                end = date.fromisoformat(fields["closing_date"])
                value = f"{date_format(start, 'MONTH_DAY_FORMAT')} – {date_format(end, 'MONTH_DAY_FORMAT')}"
            else:
                continue
            if camping.open_all_year:
                current = _("All year")
            elif camping.opening_date and camping.closing_date:
                current = (
                    f"{date_format(camping.opening_date, 'MONTH_DAY_FORMAT')} – "
                    f"{date_format(camping.closing_date, 'MONTH_DAY_FORMAT')}"
                )
            else:
                current = ""
        elif key in ("check_in_from", "check_out_until"):
            if not fields.get(key):
                continue
            value = fields[key]
            current = getattr(policy, key).strftime("%H:%M") if getattr(policy, key) else ""
            default = BookingPolicy._meta.get_field(key).default
            # Still the default time: the website knows better.
            checked = bool(default) and current == default.strftime("%H:%M")
        else:
            if fields.get(key) in (None, ""):
                continue
            value = fields[key]
            current = getattr(camping, key) or ""
        if str(current).strip().lower() == str(value).strip().lower():
            continue  # nothing new
        rows.append(
            {
                "key": key,
                "label": _field_label(key),
                "value": value,
                "current": current,
                "checked": checked or not current,
            }
        )
    return rows


def _item_type_choices():
    choices = [
        (f"acc:{key}", _("Accommodation · %(kind)s") % {"kind": label})
        for key, label, _icon in catalog.ACCOMMODATION_KINDS
    ]
    choices += [(f"svc:{key}", _("Service %(unit)s") % {"unit": label}) for key, label in catalog.SERVICE_UNITS]
    return choices


def _review_context(camping, site_import):
    data = site_import.data
    existing_facilities = set(camping.facilities.values_list("kind", flat=True))
    texts = []
    for code, parts in (data.get("texts") or {}).items():
        for part in ("tagline", "description"):
            if parts.get(part):
                current = (getattr(camping, part) or {}).get(code, "")
                texts.append(
                    {
                        "value": f"{code}:{part}",
                        "language": language_name(code),
                        "label": _("Tagline") if part == "tagline" else _("Description"),
                        "text": parts[part],
                        "current": current,
                        "checked": not current,
                    }
                )
    seasons = []
    for season in data.get("seasons", []):
        seasons.append(
            {
                **season,
                "display_name": season["name"] or dict(Season.Kind.choices).get(season["kind"] or "mid"),
                "period_dates": [
                    (date.fromisoformat(start), date.fromisoformat(end)) for start, end in season["periods"]
                ],
            }
        )
    season_names = {season["key"]: season["display_name"] for season in seasons}
    items = []
    for item in data.get("items", []):
        selected_type = (
            f"acc:{item.get('accommodation_kind')}"
            if item.get("kind") == "accommodation"
            else f"svc:{item.get('unit')}"
        )
        items.append(
            {
                **item,
                "selected_type": selected_type,
                "price_list": [
                    (season_names.get(key, key), value) for key, value in (item.get("prices") or {}).items()
                ],
            }
        )
    photos = [
        {**photo, "index": index, "checked": index < PRESELECTED_PHOTOS}
        for index, photo in enumerate(data.get("photos", []))
    ]
    return {
        "site_import": site_import,
        "data": data,
        "field_rows": _field_rows(camping, data.get("fields", {})),
        "texts": texts,
        "location_info": data.get("location_info") or {},
        "facilities": [
            {
                "key": key,
                "label": catalog.FACILITY_MAP[key]["label"],
                "icon": catalog.FACILITY_MAP[key]["icon"],
                "evidence": evidence,
                "existing": key in existing_facilities,
            }
            for key, evidence in (data.get("facilities") or {}).items()
            if key in catalog.FACILITY_MAP
        ],
        "seasons": seasons,
        "season_kinds": Season.Kind.choices,
        "items": items,
        "item_types": _item_type_choices(),
        "service_modes": catalog.SERVICE_MODES,
        "photos": photos,
        "has_logo": bool(camping.logo),
        "currency": camping.currency,
        "camping_seasons": [translate_value(season.name) for season in camping.seasons.all()],
    }


def _choices_from_post(post, data):
    return {
        "fields": post.getlist("field"),
        "texts": post.getlist("text"),
        "location_info": bool(post.get("location_info")),
        "facilities": post.getlist("facility"),
        "seasons": post.getlist("season"),
        "season_kinds": {season["key"]: post.get(f"season_kind_{season['key']}") for season in data.get("seasons", [])},
        "items": post.getlist("item"),
        "item_types": {item["key"]: post.get(f"item_type_{item['key']}") for item in data.get("items", [])},
        "item_modes": {item["key"]: post.get(f"item_mode_{item['key']}") for item in data.get("items", [])},
        "photos": [int(value) for value in post.getlist("photo") if value.isdigit()],
        "logo": bool(post.get("logo")),
    }


@camping_view(owner_only=True)
def import_review(request, camping, pk):
    site_import = get_object_or_404(SiteImport, pk=pk, camping=camping)
    if site_import.status == SiteImport.Status.APPLIED:
        if site_import.photo_queue:
            return redirect("panel:import_photos", slug=camping.slug, pk=site_import.pk)
        messages.info(request, _("This import has already been applied."))
        return redirect("panel:import", slug=camping.slug)
    if request.method == "POST":
        summary = apply_import(site_import, _choices_from_post(request.POST, site_import.data))
        messages.success(
            request,
            _(
                "Imported: %(accommodations)s accommodation types, %(services)s services, %(seasons)s seasons and "
                "%(facilities)s facilities."
            )
            % summary,
        )
        if summary["skipped_periods"]:
            messages.warning(
                request,
                _("%(count)s period(s) were not created because they overlap with existing seasons.")
                % {"count": summary["skipped_periods"]},
            )
        if site_import.photo_queue:
            return redirect("panel:import_photos", slug=camping.slug, pk=site_import.pk)
        return redirect("panel:dashboard", slug=camping.slug)
    return panel_render(request, "panel/import_review.html", _review_context(camping, site_import), section="import")


@camping_view(owner_only=True)
def import_photos(request, camping, pk):
    site_import = get_object_or_404(SiteImport, pk=pk, camping=camping)
    if request.method == "POST":
        remaining = process_photo_queue(site_import)
        if wants_json(request):
            return JsonResponse(
                {
                    "done": site_import.photos_done,
                    "failed": site_import.photos_failed,
                    "remaining": remaining,
                    "total": site_import.photos_total,
                }
            )
        return redirect("panel:import_photos", slug=camping.slug, pk=site_import.pk)
    return panel_render(request, "panel/import_photos.html", {"site_import": site_import}, section="import")


@require_POST
@camping_view(owner_only=True)
def import_photos_cancel(request, camping, pk):
    site_import = get_object_or_404(SiteImport, pk=pk, camping=camping)
    site_import.photo_queue = []
    site_import.save(update_fields=["photo_queue"])
    return redirect("panel:photos", slug=camping.slug)
