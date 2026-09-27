from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from bookings.models import BookingRequest
from core.i18n import has_translation
from core.images import ImageProcessingError, process_logo

from ..forms import AppearanceForm, LocationForm, ProfileForm, SettingsForm
from ..utils import camping_view, panel_render, user_campings


@login_required
def home(request):
    campings = list(user_campings(request.user))
    if len(campings) == 1 and not request.user.is_superuser:
        return redirect("panel:dashboard", slug=campings[0].slug)
    if not campings and request.user.is_superuser:
        return redirect("panel:platform")
    return panel_render(request, "panel/home.html", {"campings": campings})


def setup_checklist(camping):
    photos = camping.photos.count()
    accommodations = list(camping.accommodations.all())
    items = [
        {
            "done": has_translation(camping.description, camping.default_language)
            and bool(camping.phone or camping.email),
            "label": _("Describe your camping and add contact details"),
            "url_name": "panel:profile",
        },
        {
            "done": bool(camping.city and camping.latitude is not None),
            "label": _("Add the address and map location"),
            "url_name": "panel:location",
        },
        {
            "done": photos >= 3,
            "label": _("Upload at least 3 photos"),
            "url_name": "panel:photos",
        },
        {
            "done": camping.facilities.count() >= 3,
            "label": _("Tick your facilities"),
            "url_name": "panel:facilities",
        },
        {
            "done": any(acc.base_price > 0 for acc in accommodations),
            "label": _("Create your accommodation types with prices"),
            "url_name": "panel:accommodations",
        },
        {
            "done": camping.seasons.exists() or camping.services.exists(),
            "label": _("Define seasons or services and extras"),
            "url_name": "panel:seasons",
        },
        {
            "done": camping.is_published,
            "label": _("Publish your page"),
            "url_name": "panel:dashboard",
        },
    ]
    return items


@camping_view()
def dashboard(request, camping):
    today = timezone.localdate()
    requests_qs = camping.booking_requests.select_related("accommodation")
    checklist = setup_checklist(camping)
    done = sum(1 for item in checklist if item["done"])
    confirmed = requests_qs.filter(status=BookingRequest.Status.CONFIRMED)
    staying = confirmed.filter(arrival__lte=today, departure__gt=today).aggregate(
        units=Sum("units"), adults=Sum("adults"), children=Sum("children")
    )
    capacity = camping.accommodations.filter(is_active=True).aggregate(total=Sum("units"))["total"] or 0
    units_used = staying["units"] or 0
    context = {
        "today": {
            "date": today,
            "arrivals": list(confirmed.filter(arrival=today)),
            "departures": list(confirmed.filter(departure=today)),
            "guests": (staying["adults"] or 0) + (staying["children"] or 0),
            "units_used": units_used,
            "capacity": capacity,
            "occupancy": round(units_used * 100 / capacity) if capacity else 0,
        },
        "checklist": checklist,
        "progress": round(done * 100 / len(checklist)),
        "recent_requests": requests_qs[:6],
        "upcoming": requests_qs.filter(status=BookingRequest.Status.CONFIRMED, departure__gte=today).order_by(
            "arrival"
        )[:6],
        "stats": {
            "photos": camping.photos.count(),
            "accommodations": camping.accommodations.count(),
            "facilities": camping.facilities.count(),
            "requests_month": requests_qs.filter(created_at__date__gte=today.replace(day=1)).count(),
        },
    }
    return panel_render(request, "panel/dashboard.html", context, section="dashboard")


@require_POST
@camping_view(owner_only=True)
def toggle_publish(request, camping):
    camping.is_published = not camping.is_published
    camping.save(update_fields=["is_published", "updated_at"])
    if camping.is_published:
        if camping.is_approved:
            messages.success(request, _("Your page is now public."))
        else:
            messages.warning(request, _("Your page will be visible as soon as the platform approves your camping."))
    else:
        messages.info(request, _("Your page is hidden from the public."))
    return redirect("panel:dashboard", slug=camping.slug)


def _content_form_view(request, camping, form_class, template, section, success_message):
    form = form_class(request.POST or None, instance=camping, camping=camping)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, success_message)
        return redirect(f"panel:{section}", slug=camping.slug)
    return panel_render(request, template, {"form": form}, section=section)


@camping_view()
def profile(request, camping):
    return _content_form_view(
        request, camping, ProfileForm, "panel/profile.html", "profile", _("The camping details have been saved.")
    )


@camping_view()
def location(request, camping):
    return _content_form_view(
        request, camping, LocationForm, "panel/location.html", "location", _("The location has been saved.")
    )


@camping_view(owner_only=True)
def camping_settings(request, camping):
    form = SettingsForm(request.POST or None, instance=camping, allow_domain=request.user.is_superuser)
    if request.method == "POST" and form.is_valid():
        camping = form.save()
        messages.success(request, _("The settings have been saved."))
        return redirect("panel:settings", slug=camping.slug)
    return panel_render(request, "panel/settings.html", {"form": form}, section="settings")


@camping_view()
def appearance(request, camping):
    form = AppearanceForm(request.POST or None, request.FILES or None, instance=camping)
    if request.method == "POST" and form.is_valid():
        camping = form.save(commit=False)
        upload = form.cleaned_data.get("logo_file")
        try:
            if upload:
                processed = process_logo(upload)
                camping.logo.save(processed.file.name, processed.file, save=False)
            elif form.cleaned_data.get("remove_logo"):
                camping.logo = None
        except ImageProcessingError as error:
            form.add_error("logo_file", str(error))
        else:
            camping.save()
            messages.success(request, _("The appearance has been saved."))
            return redirect("panel:appearance", slug=camping.slug)
    return panel_render(request, "panel/appearance.html", {"form": form}, section="appearance")
