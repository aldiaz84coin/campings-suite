import secrets
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from campings.models import AccommodationType, Camping, Service

_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_reference():
    return "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(7))


class BookingRequest(models.Model):
    """A stay: requested from the public site or added by the camping.

    Only confirmed stays take up units of the accommodation type.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        CONFIRMED = "confirmed", _("Confirmed")
        DECLINED = "declined", _("Declined")
        CANCELLED = "cancelled", _("Cancelled")

    class Source(models.TextChoices):
        WEB = "web", _("Website")
        MANUAL = "manual", _("Added in the panel")

    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="booking_requests")
    reference = models.CharField(_("reference"), max_length=12, unique=True, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    accommodation = models.ForeignKey(
        AccommodationType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_requests",
        verbose_name=_("accommodation"),
    )
    accommodation_name = models.CharField(_("accommodation name"), max_length=200, blank=True)
    units = models.PositiveSmallIntegerField(
        _("units"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        help_text=_("How many units of this accommodation the stay takes up."),
    )
    arrival = models.DateField(_("arrival"))
    departure = models.DateField(_("departure"))
    adults = models.PositiveSmallIntegerField(_("adults"), default=2)
    children = models.PositiveSmallIntegerField(_("children"), default=0)
    pets = models.PositiveSmallIntegerField(_("pets"), default=0)
    extras = models.ManyToManyField(Service, blank=True, verbose_name=_("extras"))

    name = models.CharField(_("name"), max_length=150)
    email = models.EmailField(_("e-mail"), blank=True)
    phone = models.CharField(_("phone"), max_length=40, blank=True)
    country = models.CharField(_("country"), max_length=80, blank=True)
    message = models.TextField(_("message"), blank=True)
    language = models.CharField(_("language"), max_length=10, default=settings.LANGUAGE_CODE)

    # {language: quote} for the guest's language and the camping's language.
    quote = models.JSONField(_("price estimate"), default=dict, blank=True)
    estimated_total = models.DecimalField(_("estimated total"), max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(_("status"), max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    internal_notes = models.TextField(_("internal notes"), blank=True)
    source = models.CharField(_("source"), max_length=10, choices=Source.choices, default=Source.WEB)

    created_at = models.DateTimeField(_("received"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("booking request")
        verbose_name_plural = _("booking requests")
        indexes = [models.Index(fields=["camping", "status", "arrival"])]

    def __str__(self):
        return f"{self.reference} · {self.name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            reference = generate_reference()
            while BookingRequest.objects.filter(reference=reference).exists():
                reference = generate_reference()
            self.reference = reference
        if self.accommodation and not self.accommodation_name:
            self.accommodation_name = self.accommodation_label(self.camping.default_language)
        super().save(*args, **kwargs)

    def quote_in(self, language):
        quotes = self.quote or {}
        if "lines" in quotes:  # single quote
            return quotes
        return quotes.get(language) or quotes.get(self.camping.default_language) or next(iter(quotes.values()), {})

    @property
    def guest_quote(self):
        return self.quote_in(self.language)

    @property
    def camping_quote(self):
        return self.quote_in(self.camping.default_language)

    def accommodation_label(self, language):
        if self.accommodation is None:
            return self.accommodation_name
        with translation.override(language):
            return self.accommodation.display_name

    @property
    def nights(self):
        return (self.departure - self.arrival).days

    @property
    def guests(self):
        return self.adults + self.children

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING
