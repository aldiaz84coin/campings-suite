from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from bookings.models import BookingRequest
from campings.models import Camping, Membership
from core.urlutils import request_camping_id


def user_campings(user, request=None):
    """Campings ``user`` belongs to (only the host's camping on its own domain)."""
    if not user.is_authenticated:
        return Camping.objects.none()
    campings = Camping.objects.filter(memberships__user=user).distinct().order_by("name")
    if request_camping_id(request):
        campings = campings.filter(pk=request.domain_camping_id)
    return campings


def camping_view(owner_only=False):
    """Loads the camping from the URL and checks the user may manage it.

    Superusers can manage every camping. Non-members get a 404 so the
    existence of other campings is not revealed. On a camping's own host only
    that camping can be managed.
    """

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, slug, *args, **kwargs):
            camping = get_object_or_404(Camping, slug=slug)
            if request_camping_id(request) not in (None, camping.pk):
                raise Http404("Camping not found")
            membership = None
            if not request.user.is_superuser:
                membership = Membership.objects.filter(user=request.user, camping=camping).first()
                if membership is None:
                    raise Http404("Camping not found")
                if owner_only and not membership.is_owner:
                    raise PermissionDenied
            request.camping = camping
            request.membership = membership
            request.is_owner = request.user.is_superuser or membership.is_owner
            return view(request, camping, *args, **kwargs)

        return wrapper

    return decorator


def panel_render(request, template, context=None, section=None):
    context = dict(context or {})
    camping = context.get("camping") or getattr(request, "camping", None)
    context.setdefault("camping", camping)
    context["section"] = section
    context["my_campings"] = list(user_campings(request.user, request).only("id", "name", "slug"))
    context["is_owner"] = getattr(request, "is_owner", request.user.is_superuser)
    if camping is not None:
        context["pending_count"] = BookingRequest.objects.filter(
            camping=camping, status=BookingRequest.Status.PENDING
        ).count()
    return render(request, template, context)


def wants_json(request):
    return request.headers.get("x-requested-with") == "fetch" or "application/json" in request.headers.get("accept", "")


def platform_only(request):
    """Platform administration and sign-up do not exist on a camping's own host."""
    if request_camping_id(request):
        raise Http404("Not available on this address")
