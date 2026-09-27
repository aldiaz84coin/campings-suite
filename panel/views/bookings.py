import calendar as pycalendar
import csv
from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from bookings.emails import send_status_email
from bookings.forms import BookingStatusForm, ManualBookingForm
from bookings.models import BookingRequest
from campings.pricing import available_units

from ..utils import camping_view, panel_render

STATUS_TABS = ("pending", "confirmed", "declined", "cancelled", "all")


def _filtered_bookings(request, camping):
    """Bookings of ``camping`` filtered by the list's query parameters."""
    params = request.GET
    bookings = camping.booking_requests.select_related("accommodation")
    filters = {"status": params.get("status", "pending"), "q": params.get("q", "").strip()}
    if filters["status"] in BookingRequest.Status.values:
        bookings = bookings.filter(status=filters["status"])
    else:
        filters["status"] = "all"
    if filters["q"]:
        q = filters["q"]
        bookings = bookings.filter(
            Q(name__icontains=q) | Q(email__icontains=q) | Q(reference__icontains=q) | Q(phone__icontains=q)
        )
    day = parse_date(params.get("date", "") or "")
    if day:
        bookings = bookings.filter(arrival__lte=day, departure__gt=day)
        filters["date"] = day
    accommodation_id = params.get("accommodation", "")
    if accommodation_id.isdigit():
        accommodation = camping.accommodations.filter(pk=accommodation_id).first()
        if accommodation:
            bookings = bookings.filter(accommodation=accommodation)
            filters["accommodation"] = accommodation
    return bookings, filters


@camping_view()
def booking_list(request, camping):
    bookings, filters = _filtered_bookings(request, camping)
    counts = dict(
        camping.booking_requests.values_list("status").annotate(total=Count("id")).values_list("status", "total")
    )
    labels = dict(BookingRequest.Status.choices)
    labels["all"] = _("All")
    page = Paginator(bookings, 25).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "bookings": page.object_list,
        "status": filters["status"],
        "q": filters["q"],
        "filter_date": filters.get("date"),
        "filter_accommodation": filters.get("accommodation"),
        "tabs": [(key, labels[key], counts.get(key) if key != "all" else sum(counts.values())) for key in STATUS_TABS],
        "export_query": request.GET.urlencode(),
    }
    return panel_render(request, "panel/bookings.html", context, section="bookings")


@camping_view()
def booking_export(request, camping):
    bookings, _filters = _filtered_bookings(request, camping)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{camping.slug}-bookings.csv"'
    response.write("﻿")  # BOM so that Excel opens UTF-8 correctly
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        [
            _("Reference"),
            _("Status"),
            _("Source"),
            _("Received"),
            _("Arrival"),
            _("Departure"),
            _("Nights"),
            _("Accommodation"),
            _("Units"),
            _("Adults"),
            _("Children"),
            _("Pets"),
            _("Name"),
            _("E-mail"),
            _("Phone"),
            _("Country"),
            _("Language"),
            _("Estimated total"),
            _("Message"),
            _("Internal notes"),
        ]
    )
    for booking in bookings.order_by("arrival", "pk"):
        writer.writerow(
            [
                booking.reference,
                booking.get_status_display(),
                booking.get_source_display(),
                timezone.localtime(booking.created_at).strftime("%Y-%m-%d %H:%M"),
                booking.arrival.isoformat(),
                booking.departure.isoformat(),
                booking.nights,
                booking.accommodation_name,
                booking.units,
                booking.adults,
                booking.children,
                booking.pets,
                booking.name,
                booking.email,
                booking.phone,
                booking.country,
                booking.language,
                booking.estimated_total if booking.estimated_total is not None else "",
                booking.message,
                booking.internal_notes,
            ]
        )
    return response


@camping_view()
def booking_detail(request, camping, pk):
    booking = get_object_or_404(BookingRequest.objects.select_related("accommodation"), pk=pk, camping=camping)
    previous_status = booking.status
    form = BookingStatusForm(request.POST or None, instance=booking)
    if request.method == "POST" and form.is_valid():
        booking = form.save()
        if booking.status != previous_status:
            messages.success(request, _("Status changed to “%(status)s”.") % {"status": booking.get_status_display()})
            if form.cleaned_data.get("notify_guest") and booking.status != BookingRequest.Status.PENDING:
                if send_status_email(booking):
                    messages.info(request, _("We have sent an e-mail to the guest."))
        else:
            messages.success(request, _("Notes saved."))
        return redirect("panel:booking_detail", slug=camping.slug, pk=booking.pk)

    free_units = None
    if booking.accommodation_id and booking.status != BookingRequest.Status.CONFIRMED:
        free_units = available_units(booking.accommodation, booking.arrival, booking.departure, exclude_pk=booking.pk)
    context = {
        "booking": booking,
        "form": form,
        "free_units": free_units,
        "quote": booking.camping_quote,
        "overlapping": camping.booking_requests.filter(
            accommodation=booking.accommodation,
            status=BookingRequest.Status.CONFIRMED,
            arrival__lt=booking.departure,
            departure__gt=booking.arrival,
        ).exclude(pk=booking.pk)[:10]
        if booking.accommodation_id
        else [],
    }
    return panel_render(request, "panel/booking_detail.html", context, section="bookings")


def _booking_form_view(request, camping, booking=None):
    initial = {}
    if booking is None:
        for key in ("arrival", "departure"):
            if parse_date(request.GET.get(key, "") or ""):
                initial[key] = request.GET[key]
        if initial.get("arrival") and not initial.get("departure"):
            initial["departure"] = (parse_date(initial["arrival"]) + timedelta(days=1)).isoformat()
        if request.GET.get("accommodation", "").isdigit():
            initial["accommodation"] = int(request.GET["accommodation"])
    form = ManualBookingForm(request.POST or None, instance=booking, camping=camping, initial=initial)
    if request.method == "POST" and form.is_valid():
        booking = form.save()
        messages.success(request, _("The booking %(reference)s has been saved.") % {"reference": booking.reference})
        return redirect("panel:booking_detail", slug=camping.slug, pk=booking.pk)
    return panel_render(
        request,
        "panel/booking_form.html",
        {"form": form, "booking": booking, "quote": form.quote.as_dict() if form.quote else None},
        section="bookings",
    )


@camping_view()
def booking_create(request, camping):
    return _booking_form_view(request, camping)


@camping_view()
def booking_edit(request, camping, pk):
    booking = get_object_or_404(BookingRequest, pk=pk, camping=camping)
    return _booking_form_view(request, camping, booking)


def _month_from(value, today):
    try:
        year, month = (int(part) for part in (value or "").split("-"))
        return date(year, month, 1)
    except (TypeError, ValueError):
        return today.replace(day=1)


@camping_view()
def booking_calendar(request, camping):
    """Occupancy per accommodation type and night for one month."""
    today = timezone.localdate()
    first = _month_from(request.GET.get("month"), today)
    days_in_month = pycalendar.monthrange(first.year, first.month)[1]
    days = [first + timedelta(days=offset) for offset in range(days_in_month)]
    last = days[-1]

    accommodations = list(camping.accommodations.all())
    stays = list(
        camping.booking_requests.filter(
            status__in=[BookingRequest.Status.CONFIRMED, BookingRequest.Status.PENDING],
            accommodation__isnull=False,
            arrival__lte=last,
            departure__gt=first,
        ).only("id", "accommodation_id", "arrival", "departure", "units", "status", "name")
    )

    rows = []
    totals = [0] * len(days)
    capacity = sum(acc.units for acc in accommodations if acc.is_active)
    for accommodation in accommodations:
        own = [stay for stay in stays if stay.accommodation_id == accommodation.pk]
        cells = []
        for index, day in enumerate(days):
            present = [stay for stay in own if stay.arrival <= day < stay.departure]
            confirmed = [stay for stay in present if stay.status == BookingRequest.Status.CONFIRMED]
            used = sum(stay.units for stay in confirmed)
            pending = len(present) - len(confirmed)
            if accommodation.is_active:
                totals[index] += used
            if used == 0:
                level = "free"
            elif used < accommodation.units:
                level = "partial"
            elif used == accommodation.units:
                level = "full"
            else:
                level = "over"
            cells.append(
                {
                    "day": day,
                    "used": used,
                    "pending": pending,
                    "level": level,
                    "names": ", ".join(stay.name for stay in present),
                }
            )
        rows.append({"accommodation": accommodation, "cells": cells})

    occupancy = [round(used * 100 / capacity) if capacity else 0 for used in totals]
    previous_month = (first - timedelta(days=1)).replace(day=1)
    next_month = last + timedelta(days=1)
    context = {
        "rows": rows,
        "days": days,
        "today": today,
        "month_label": date_format(first, "YEAR_MONTH_FORMAT"),
        "previous_month": previous_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
        "this_month": today.strftime("%Y-%m"),
        "day_totals": list(zip(days, occupancy, strict=True)),
    }
    return panel_render(request, "panel/calendar.html", context, section="calendar")
