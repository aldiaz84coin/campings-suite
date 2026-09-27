"""Facilities, accommodation, services, seasons, prices and booking policies."""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from campings import catalog
from campings.models import (
    AccommodationRate,
    AccommodationType,
    Facility,
    Season,
    Service,
    ServiceRate,
)
from core.i18n import translate_value

from ..forms import AccommodationForm, FacilityForm, PolicyForm, SeasonForm, ServiceForm
from ..utils import camping_view, panel_render

# --- Generic helpers ---------------------------------------------------------------


def _edit_object(request, camping, *, form_class, instance, template, section, list_url, saved_message, extra=None):
    form = form_class(request.POST or None, instance=instance, camping=camping)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, saved_message)
        return redirect(list_url, slug=camping.slug)
    context = {"form": form, "object": instance, "is_new": instance.pk is None}
    if "photos" in form.fields:
        values = form["photos"].value() or []
        context["selected_photo_ids"] = {int(value) for value in values if str(value).isdigit()}
    context.update(extra or {})
    return panel_render(request, template, context, section=section)


def _delete_object(request, camping, obj, list_url, message):
    obj.delete()
    messages.success(request, message)
    return redirect(list_url, slug=camping.slug)


# --- Facilities --------------------------------------------------------------------


@camping_view()
def facilities(request, camping):
    existing = {f.kind: f for f in camping.facilities.exclude(kind=Facility.CUSTOM)}
    if request.method == "POST":
        selected = set(request.POST.getlist("facilities")) & set(catalog.FACILITY_MAP)
        paid = set(request.POST.getlist("paid"))
        with transaction.atomic():
            for kind, facility in existing.items():
                if kind not in selected:
                    facility.delete()
                elif facility.is_paid != (kind in paid):
                    facility.is_paid = kind in paid
                    facility.save(update_fields=["is_paid"])
            order = [key for key, *_rest in catalog.FACILITIES]
            for kind in selected - set(existing):
                Facility.objects.create(camping=camping, kind=kind, is_paid=kind in paid, position=order.index(kind))
        messages.success(request, _("Your facilities have been saved."))
        return redirect("panel:facilities", slug=camping.slug)

    groups = []
    for group_key, group_label in catalog.FACILITY_GROUPS:
        items = [
            {
                "key": key,
                "label": label,
                "icon": icon,
                "facility": existing.get(key),
            }
            for key, label, icon, group in catalog.FACILITIES
            if group == group_key
        ]
        groups.append({"key": group_key, "label": group_label, "items": items})
    context = {
        "groups": groups,
        "custom_facilities": camping.facilities.filter(kind=Facility.CUSTOM),
    }
    return panel_render(request, "panel/facilities.html", context, section="facilities")


@camping_view()
def facility_create(request, camping):
    return _edit_object(
        request,
        camping,
        form_class=FacilityForm,
        instance=Facility(camping=camping, kind=Facility.CUSTOM, position=100),
        template="panel/facility_form.html",
        section="facilities",
        list_url="panel:facilities",
        saved_message=_("The facility has been added."),
    )


@camping_view()
def facility_edit(request, camping, pk):
    return _edit_object(
        request,
        camping,
        form_class=FacilityForm,
        instance=get_object_or_404(Facility, pk=pk, camping=camping),
        template="panel/facility_form.html",
        section="facilities",
        list_url="panel:facilities",
        saved_message=_("The facility has been saved."),
    )


@require_POST
@camping_view()
def facility_delete(request, camping, pk):
    facility = get_object_or_404(Facility, pk=pk, camping=camping)
    return _delete_object(request, camping, facility, "panel:facilities", _("The facility has been removed."))


# --- Accommodation -----------------------------------------------------------------


@camping_view()
def accommodations(request, camping):
    items = camping.accommodations.prefetch_related("rates", "photos")
    return panel_render(request, "panel/accommodations.html", {"accommodations": items}, section="accommodations")


@camping_view()
def accommodation_create(request, camping):
    position = camping.accommodations.count()
    return _edit_object(
        request,
        camping,
        form_class=AccommodationForm,
        instance=AccommodationType(camping=camping, position=position),
        template="panel/accommodation_form.html",
        section="accommodations",
        list_url="panel:accommodations",
        saved_message=_("The accommodation type has been created."),
    )


@camping_view()
def accommodation_edit(request, camping, pk):
    return _edit_object(
        request,
        camping,
        form_class=AccommodationForm,
        instance=get_object_or_404(AccommodationType, pk=pk, camping=camping),
        template="panel/accommodation_form.html",
        section="accommodations",
        list_url="panel:accommodations",
        saved_message=_("The accommodation type has been saved."),
    )


@require_POST
@camping_view()
def accommodation_delete(request, camping, pk):
    accommodation = get_object_or_404(AccommodationType, pk=pk, camping=camping)
    return _delete_object(
        request, camping, accommodation, "panel:accommodations", _("The accommodation type has been deleted.")
    )


# --- Services ---------------------------------------------------------------------


@camping_view()
def services(request, camping):
    items = camping.services.prefetch_related("rates", "accommodations")
    return panel_render(request, "panel/services.html", {"services": items}, section="services")


@camping_view()
def service_create(request, camping):
    return _edit_object(
        request,
        camping,
        form_class=ServiceForm,
        instance=Service(camping=camping, position=camping.services.count()),
        template="panel/service_form.html",
        section="services",
        list_url="panel:services",
        saved_message=_("The service has been created."),
    )


@camping_view()
def service_edit(request, camping, pk):
    return _edit_object(
        request,
        camping,
        form_class=ServiceForm,
        instance=get_object_or_404(Service, pk=pk, camping=camping),
        template="panel/service_form.html",
        section="services",
        list_url="panel:services",
        saved_message=_("The service has been saved."),
    )


@require_POST
@camping_view()
def service_delete(request, camping, pk):
    service = get_object_or_404(Service, pk=pk, camping=camping)
    return _delete_object(request, camping, service, "panel:services", _("The service has been deleted."))


# --- Seasons ---------------------------------------------------------------------


@camping_view()
def seasons(request, camping):
    return panel_render(request, "panel/seasons.html", {"seasons": camping.seasons.all()}, section="seasons")


@camping_view()
def season_create(request, camping):
    return _edit_object(
        request,
        camping,
        form_class=SeasonForm,
        instance=Season(camping=camping),
        template="panel/season_form.html",
        section="seasons",
        list_url="panel:seasons",
        saved_message=_("The season has been created."),
    )


@camping_view()
def season_edit(request, camping, pk):
    return _edit_object(
        request,
        camping,
        form_class=SeasonForm,
        instance=get_object_or_404(Season, pk=pk, camping=camping),
        template="panel/season_form.html",
        section="seasons",
        list_url="panel:seasons",
        saved_message=_("The season has been saved."),
    )


@require_POST
@camping_view()
def season_delete(request, camping, pk):
    season = get_object_or_404(Season, pk=pk, camping=camping)
    return _delete_object(request, camping, season, "panel:seasons", _("The season has been deleted."))


def _shift_year(day, years):
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February
        return date(day.year + years, 2, 28)


@require_POST
@camping_view()
def seasons_copy(request, camping):
    """Duplicate the latest year's seasons (and their prices) one year later."""
    all_seasons = list(camping.seasons.prefetch_related("accommodation_rates", "service_rates"))
    if not all_seasons:
        messages.info(request, _("There are no seasons to copy yet."))
        return redirect("panel:seasons", slug=camping.slug)
    last_year = max(season.start_date.year for season in all_seasons)
    copied = 0
    with transaction.atomic():
        for season in [s for s in all_seasons if s.start_date.year == last_year]:
            start, end = _shift_year(season.start_date, 1), _shift_year(season.end_date, 1)
            overlaps = camping.seasons.filter(start_date__lte=end, end_date__gte=start).exists()
            if overlaps:
                continue
            new_season = Season.objects.create(
                camping=camping,
                name=season.name,
                start_date=start,
                end_date=end,
                min_nights=season.min_nights,
                color=season.color,
            )
            AccommodationRate.objects.bulk_create(
                AccommodationRate(accommodation_id=r.accommodation_id, season=new_season, price=r.price)
                for r in season.accommodation_rates.all()
            )
            ServiceRate.objects.bulk_create(
                ServiceRate(service_id=r.service_id, season=new_season, price=r.price)
                for r in season.service_rates.all()
            )
            copied += 1
    if copied:
        messages.success(
            request,
            _("%(count)s season(s) copied to %(year)s with their prices.") % {"count": copied, "year": last_year + 1},
        )
    else:
        messages.info(request, _("The seasons of %(year)s already exist.") % {"year": last_year + 1})
    return redirect("panel:seasons", slug=camping.slug)


# --- Price table -----------------------------------------------------------------


def _parse_price(raw):
    raw = (raw or "").strip().replace("€", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")
    value = Decimal(raw)
    if value < 0 or value >= Decimal("1000000"):
        raise InvalidOperation
    return value.quantize(Decimal("0.01"))


def _sync_rates(owner, rate_model, owner_field, seasons, data, prefix, errors, label):
    existing = {rate.season_id: rate for rate in owner.rates.all()}
    base_key = f"{prefix}-{owner.pk}-base"
    try:
        base = _parse_price(data.get(base_key))
    except InvalidOperation:
        errors.append(_("Invalid price for %(item)s.") % {"item": label})
        return
    base_field = "base_price" if prefix == "acc" else "price"
    if base is not None and getattr(owner, base_field) != base:
        setattr(owner, base_field, base)
        owner.save(update_fields=[base_field])
    for season in seasons:
        key = f"{prefix}-{owner.pk}-{season.pk}"
        try:
            price = _parse_price(data.get(key))
        except InvalidOperation:
            errors.append(
                _("Invalid price for %(item)s in %(season)s.") % {"item": label, "season": translate_value(season.name)}
            )
            continue
        rate = existing.get(season.pk)
        if price is None:
            if rate is not None:
                rate.delete()
        elif rate is None:
            rate_model.objects.create(**{owner_field: owner, "season": season, "price": price})
        elif rate.price != price:
            rate.price = price
            rate.save(update_fields=["price"])


@camping_view()
def prices(request, camping):
    # Past seasons keep their prices but are no longer editable here.
    seasons = list(camping.seasons.filter(end_date__gte=timezone.localdate()))
    accommodation_list = list(camping.accommodations.prefetch_related("rates"))
    service_list = list(camping.services.exclude(mode="included").prefetch_related("rates"))

    if request.method == "POST":
        errors = []
        with transaction.atomic():
            for accommodation in accommodation_list:
                _sync_rates(
                    accommodation,
                    AccommodationRate,
                    "accommodation",
                    seasons,
                    request.POST,
                    "acc",
                    errors,
                    accommodation.display_name,
                )
            for service in service_list:
                _sync_rates(service, ServiceRate, "service", seasons, request.POST, "svc", errors, service.display_name)
        for error in errors:
            messages.error(request, error)
        if not errors:
            messages.success(request, _("Prices saved."))
        return redirect("panel:prices", slug=camping.slug)

    def rows(items, prefix, base_attr):
        result = []
        for item in items:
            rates = item.rate_map()
            result.append(
                {
                    "item": item,
                    "base_name": f"{prefix}-{item.pk}-base",
                    "base": getattr(item, base_attr),
                    "cells": [
                        {"name": f"{prefix}-{item.pk}-{season.pk}", "value": rates.get(season.pk, "")}
                        for season in seasons
                    ],
                }
            )
        return result

    context = {
        "seasons": seasons,
        "accommodation_rows": rows(accommodation_list, "acc", "base_price"),
        "service_rows": rows(service_list, "svc", "price"),
    }
    return panel_render(request, "panel/prices.html", context, section="prices")


# --- Policies ---------------------------------------------------------------------


@camping_view()
def policies(request, camping):
    policy = camping.get_policy()
    form = PolicyForm(request.POST or None, instance=policy, camping=camping)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Your booking policies have been saved."))
        return redirect("panel:policies", slug=camping.slug)
    return panel_render(request, "panel/policies.html", {"form": form}, section="policies")
