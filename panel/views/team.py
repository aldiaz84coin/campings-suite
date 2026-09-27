import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from bookings.emails import send_templated_email
from campings.models import Membership
from core.urlutils import camping_panel_url

from ..forms import InviteForm
from ..utils import camping_view, panel_render

logger = logging.getLogger(__name__)
User = get_user_model()


def invite_user(request, camping, email, role, first_name=""):
    """Adds ``email`` to the camping team, creating the user if needed.

    Returns ``(membership, set_password_url)``; the URL is only generated for
    brand-new users (they choose their password through it).
    """
    user = User.objects.filter(email__iexact=email).first()
    set_password_url = None
    if user is None:
        user = User.objects.create_user(email=email, password=None, first_name=first_name)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        set_password_url = camping_panel_url(
            request, camping, reverse("panel:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        )
    membership, _created = Membership.objects.get_or_create(user=user, camping=camping, defaults={"role": role})
    send_templated_email(
        _("You have been invited to manage %(camping)s") % {"camping": camping.name},
        "emails/team_invite.txt",
        {
            "camping": camping,
            "platform_name": settings.PLATFORM_NAME,
            "set_password_url": set_password_url,
            "login_url": camping_panel_url(request, camping, reverse("panel:login")),
        },
        [user.email],
    )
    return membership, set_password_url


@camping_view()
def team(request, camping):
    form = InviteForm(request.POST or None, camping=camping)
    invite_link = None
    if request.method == "POST":
        if not request.is_owner:
            messages.error(request, _("Only owners can invite people."))
            return redirect("panel:team", slug=camping.slug)
        if form.is_valid():
            membership, invite_link = invite_user(
                request, camping, form.cleaned_data["email"], form.cleaned_data["role"]
            )
            messages.success(request, _("%(email)s has been added to the team.") % {"email": membership.user.email})
            if not invite_link:
                return redirect("panel:team", slug=camping.slug)
            form = InviteForm(camping=camping)
    members = camping.memberships.select_related("user").order_by("role", "user__email")
    return panel_render(
        request, "panel/team.html", {"form": form, "members": members, "invite_link": invite_link}, section="team"
    )


@require_POST
@camping_view(owner_only=True)
def team_remove(request, camping, pk):
    membership = get_object_or_404(Membership, pk=pk, camping=camping)
    owners = camping.memberships.filter(role=Membership.Role.OWNER)
    if membership.is_owner and owners.count() == 1:
        messages.error(request, _("A camping needs at least one owner."))
    else:
        membership.delete()
        messages.success(request, _("%(email)s no longer has access.") % {"email": membership.user.email})
        if membership.user_id == request.user.pk:
            return redirect("panel:home")
    return redirect("panel:team", slug=camping.slug)
