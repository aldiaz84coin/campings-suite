from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from bookings.models import BookingRequest
from campings.models import Camping, Membership

from ..forms import PlatformCampingForm
from ..utils import panel_render
from .team import invite_user


def superuser_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


@superuser_required
def platform(request):
    q = request.GET.get("q", "").strip()
    show = request.GET.get("show", "")
    campings = Camping.objects.annotate(
        pending=Count("booking_requests", filter=Q(booking_requests__status=BookingRequest.Status.PENDING)),
        photo_count=Count("photos", distinct=True),
    ).prefetch_related("memberships__user")
    if q:
        campings = campings.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(memberships__user__email__icontains=q)).distinct()
    if show == "pending":
        campings = campings.filter(is_approved=False)
    page = Paginator(campings.order_by("-created_at"), 30).get_page(request.GET.get("page"))
    stats = {
        "total": Camping.objects.count(),
        "public": Camping.objects.filter(is_published=True, is_approved=True).count(),
        "pending_approval": Camping.objects.filter(is_approved=False).count(),
        "requests": BookingRequest.objects.count(),
    }
    return panel_render(
        request, "panel/platform.html", {"page": page, "campings": page.object_list, "q": q, "show": show, "stats": stats},
        section="platform",
    )


@superuser_required
def platform_new(request):
    form = PlatformCampingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        language = form.cleaned_data["default_language"]
        with transaction.atomic():
            camping = Camping.objects.create(
                name=form.cleaned_data["name"],
                default_language=language,
                languages=[language, "en"] if language != "en" else ["en", "es"],
                email=form.cleaned_data["owner_email"],
                is_approved=True,
            )
            _membership, link = invite_user(
                request, camping, form.cleaned_data["owner_email"], Membership.Role.OWNER,
                first_name=form.cleaned_data.get("owner_name", ""),
            )
        messages.success(request, _("Camping “%(name)s” created.") % {"name": camping.name})
        if link:
            messages.info(request, _("Send this link to the owner so they can choose a password: %(link)s") % {"link": link})
        return redirect("panel:platform")
    return panel_render(request, "panel/platform_new.html", {"form": form}, section="platform")


@require_POST
@superuser_required
def platform_toggle_approval(request, slug):
    camping = get_object_or_404(Camping, slug=slug)
    camping.is_approved = not camping.is_approved
    camping.save(update_fields=["is_approved", "updated_at"])
    if camping.is_approved:
        messages.success(request, _("“%(name)s” is approved.") % {"name": camping.name})
    else:
        messages.warning(request, _("“%(name)s” is suspended and hidden from the public.") % {"name": camping.name})
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("panel:platform")
