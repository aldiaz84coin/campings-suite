import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy, translate_url
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from bookings.emails import sender_for
from campings.models import Camping, Membership
from core.urlutils import platform_url, request_camping_id

from ..forms import AccountForm, EmailAuthenticationForm, PanelPasswordResetForm, SignupForm
from ..utils import panel_render, platform_only

logger = logging.getLogger(__name__)
User = get_user_model()


class LoginView(auth_views.LoginView):
    template_name = "panel/auth/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        url = super().get_success_url()
        language = self.request.user.preferred_language
        if language and language != get_language():
            url = translate_url(url, language)
        return url


class LogoutView(auth_views.LogoutView):
    def get_default_redirect_url(self):
        # Back to the camping's website on its own address, else to the login.
        return reverse("public:home" if request_camping_id(self.request) else "panel:login")


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "panel/auth/password_reset.html"
    form_class = PanelPasswordResetForm
    email_template_name = "emails/password_reset.txt"
    subject_template_name = "emails/password_reset_subject.txt"
    success_url = reverse_lazy("panel:password_reset_done")

    def form_valid(self, form):
        camping = Camping.objects.filter(pk=request_camping_id(self.request)).first()
        self.extra_email_context = {"platform_name": camping.name if camping else settings.PLATFORM_NAME}
        if camping:
            self.from_email = sender_for(camping)
        return super().form_valid(form)


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "panel/auth/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "panel/auth/password_reset_confirm.html"
    success_url = reverse_lazy("panel:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "panel/auth/password_reset_complete.html"


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "panel/account_password.html"
    success_url = reverse_lazy("panel:account")

    def form_valid(self, form):
        messages.success(self.request, _("Your password has been changed."))
        return super().form_valid(form)

    def render_to_response(self, context, **response_kwargs):
        return panel_render(self.request, self.template_name, context, section="account")


def signup(request):
    platform_only(request)
    if not settings.SIGNUP_ENABLED:
        raise Http404("Sign-up is disabled")
    if request.user.is_authenticated:
        return redirect("panel:home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        language = get_language() or settings.LANGUAGE_CODE
        with transaction.atomic():
            user = User.objects.create_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data["first_name"],
                preferred_language=language,
            )
            camping = Camping.objects.create(
                name=form.cleaned_data["camping_name"],
                default_language=language,
                languages=[language, "en"] if language != "en" else ["en", "es"],
                email=user.email,
                is_approved=not settings.SIGNUP_REQUIRES_APPROVAL,
            )
            Membership.objects.create(user=user, camping=camping, role=Membership.Role.OWNER)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        _notify_new_signup(request, camping, user)
        messages.success(request, _("Welcome! Your camping has been created. Let's complete its page."))
        return redirect("panel:dashboard", slug=camping.slug)
    return panel_render(request, "panel/auth/signup.html", {"form": form})


def _notify_new_signup(request, camping, user):
    recipients = list(User.objects.filter(is_superuser=True, is_active=True).values_list("email", flat=True))
    if not recipients:
        return
    link = platform_url(request, reverse("panel:platform"))
    try:
        send_mail(
            f"[{settings.PLATFORM_NAME}] {camping.name}",
            f"{user.email} · {camping.name}\n{link}",
            settings.DEFAULT_FROM_EMAIL,
            recipients,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Could not notify the new sign-up")


def account(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('panel:login')}?next={request.path}")
    form = AccountForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Your details have been saved."))
        language = form.cleaned_data.get("preferred_language")
        target = reverse("panel:account")
        return redirect(translate_url(target, language) if language else target)
    return panel_render(request, "panel/account.html", {"form": form}, section="account")
