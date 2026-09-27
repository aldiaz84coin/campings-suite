from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from bookings.models import BookingRequest
from campings.models import Camping, Membership


def user_campings(user):
    if not user.is_authenticated:
        return Camping.objects.none()
    return Camping.objects.filter(memberships__user=user).distinct().order_by("name")


def camping_view(owner_only=False):
    """Loads the camping from the URL and checks the user may manage it.

    Superusers can manage every camping. Non-members get a 404 so the
    existence of other campings is not revealed.
    """

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, slug, *args, **kwargs):
            camping = get_object_or_404(Camping, slug=slug)
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
    context["my_campings"] = list(user_campings(request.user).only("id", "name", "slug"))
    context["is_owner"] = getattr(request, "is_owner", request.user.is_superuser)
    if camping is not None:
        context["pending_count"] = BookingRequest.objects.filter(
            camping=camping, status=BookingRequest.Status.PENDING
        ).count()
    return render(request, template, context)


def wants_json(request):
    return request.headers.get("x-requested-with") == "fetch" or "application/json" in request.headers.get(
        "accept", ""
    )
