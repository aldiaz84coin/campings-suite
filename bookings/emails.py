"""E-mail notifications for booking requests.

Each message is rendered in the recipient's language. Failures are logged
and never break the request (e-mail is optional, see ``EMAIL_URL``).
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation

logger = logging.getLogger(__name__)


def platform_url(request, path):
    """Absolute URL on the platform host (not on a camping's own domain)."""
    if settings.PLATFORM_URL:
        return f"{settings.PLATFORM_URL}{path}"
    if request is not None and not getattr(request, "domain_camping_id", None):
        return request.build_absolute_uri(path)
    return path


def send_templated_email(subject, template, context, to, reply_to=None):
    if not to:
        return False
    body = render_to_string(template, context)
    message = EmailMessage(
        subject=" ".join(subject.split()),
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        reply_to=reply_to or None,
    )
    try:
        message.send()
    except Exception:  # noqa: BLE001 - never lose a booking because of SMTP
        logger.exception("Could not send e-mail %s to %s", template, to)
        return False
    return True


def _panel_booking_url(request, booking):
    with translation.override(booking.camping.default_language):
        path = reverse(
            "panel:booking_detail",
            kwargs={"slug": booking.camping.slug, "pk": booking.pk},
            urlconf=settings.ROOT_URLCONF,
        )
    return platform_url(request, path)


def send_new_booking_emails(request, booking):
    camping = booking.camping
    context = {"booking": booking, "camping": camping, "platform_name": settings.PLATFORM_NAME}

    with translation.override(camping.default_language):
        context["panel_url"] = _panel_booking_url(request, booking)
        context["quote"] = booking.camping_quote
        context["accommodation_name"] = booking.accommodation_label(camping.default_language)
        send_templated_email(
            translation.gettext("New booking request %(reference)s") % {"reference": booking.reference},
            "emails/booking_new_camping.txt",
            context,
            [camping.booking_email] if camping.booking_email else [],
            reply_to=[booking.email],
        )

    with translation.override(booking.language):
        context = {**context, "quote": booking.guest_quote, "accommodation_name": booking.accommodation_label(booking.language)}
        send_templated_email(
            translation.gettext("We have received your booking request at %(camping)s") % {"camping": camping.name},
            "emails/booking_new_guest.txt",
            context,
            [booking.email],
            reply_to=[camping.booking_email] if camping.booking_email else None,
        )


def send_status_email(booking):
    camping = booking.camping
    context = {
        "booking": booking,
        "camping": camping,
        "platform_name": settings.PLATFORM_NAME,
        "quote": booking.guest_quote,
        "accommodation_name": booking.accommodation_label(booking.language),
    }
    with translation.override(booking.language):
        return send_templated_email(
            translation.gettext("Your booking request %(reference)s at %(camping)s: %(status)s")
            % {"reference": booking.reference, "camping": camping.name, "status": booking.get_status_display()},
            "emails/booking_status_guest.txt",
            context,
            [booking.email],
            reply_to=[camping.booking_email] if camping.booking_email else None,
        )
