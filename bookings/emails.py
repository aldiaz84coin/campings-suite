"""E-mail notifications for booking requests.

Each message is rendered in the recipient's language. Failures are logged
and never break the request (e-mail is optional, see ``EMAIL_URL``).
"""

import logging
from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation

from core.urlutils import camping_panel_url

logger = logging.getLogger(__name__)


def sender_for(camping):
    """``From`` header showing the camping's name with the platform address.

    Guests see e-mails as coming from the camping (replies go to the camping
    through ``Reply-To``) while the platform address keeps SPF/DKIM valid.
    """
    _name, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    return formataddr((camping.name, address)) if address else settings.DEFAULT_FROM_EMAIL


def send_templated_email(subject, template, context, to, reply_to=None, from_email=None):
    if not to:
        return False
    body = render_to_string(template, context)
    message = EmailMessage(
        subject=" ".join(subject.split()),
        body=body,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
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
    return camping_panel_url(request, booking.camping, path)


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
        context = {
            **context,
            "quote": booking.guest_quote,
            "accommodation_name": booking.accommodation_label(booking.language),
        }
        send_templated_email(
            translation.gettext("We have received your booking request at %(camping)s") % {"camping": camping.name},
            "emails/booking_new_guest.txt",
            context,
            [booking.email],
            reply_to=[camping.booking_email] if camping.booking_email else None,
            from_email=sender_for(camping),
        )


def send_status_email(booking):
    if not booking.email:
        return False
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
            from_email=sender_for(camping),
        )
