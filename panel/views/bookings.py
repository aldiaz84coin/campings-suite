from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _

from bookings.emails import send_status_email
from bookings.forms import BookingStatusForm
from bookings.models import BookingRequest
from campings.pricing import available_units

from ..utils import camping_view, panel_render


@camping_view()
def booking_list(request, camping):
    status = request.GET.get("status", "pending")
    q = request.GET.get("q", "").strip()
    bookings = camping.booking_requests.select_related("accommodation")
    counts = dict(bookings.values_list("status").annotate(total=Count("id")).values_list("status", "total"))
    if status in BookingRequest.Status.values:
        bookings = bookings.filter(status=status)
    else:
        status = "all"
    if q:
        bookings = bookings.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(reference__icontains=q))
    page = Paginator(bookings, 25).get_page(request.GET.get("page"))
    tabs = [("pending", _("Pending")), ("confirmed", _("Confirmed")), ("declined", _("Declined")),
            ("cancelled", _("Cancelled")), ("all", _("All"))]
    context = {
        "page": page,
        "bookings": page.object_list,
        "status": status,
        "q": q,
        "tabs": [(key, label, counts.get(key) if key != "all" else sum(counts.values())) for key, label in tabs],
    }
    return panel_render(request, "panel/bookings.html", context, section="bookings")


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
