from datetime import time
from decimal import Decimal
from urllib.parse import quote_plus

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.fields import TranslatedField
from core.i18n import platform_language_codes, translate_value

from . import catalog

hex_color_validator = RegexValidator(r"^#[0-9a-fA-F]{6}$", _("Use a colour code like #2f6f4e."))
domain_validator = RegexValidator(
    r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$",
    _("Enter a domain such as www.mycamping.com (without https://)."),
)

# The slug is also the camping's subdomain (see CAMPING_DOMAIN_SUFFIX), so it
# must be a valid DNS label.
slug_validator = RegexValidator(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    _("Use lowercase letters, numbers and hyphens (up to 63 characters, not starting or ending with a hyphen)."),
)

RESERVED_SLUGS = {
    "admin",
    "api",
    "app",
    "assets",
    "blog",
    "camping",
    "campings",
    "cdn",
    "docs",
    "ftp",
    "help",
    "imap",
    "login",
    "logout",
    "mail",
    "media",
    "panel",
    "pop",
    "signup",
    "smtp",
    "static",
    "status",
    "superadmin",
    "support",
    "webmail",
    "www",
}

NON_NEGATIVE = [MinValueValidator(Decimal("0"))]
PERCENT = [MinValueValidator(0), MaxValueValidator(100)]


def default_languages():
    return [settings.LANGUAGE_CODE]


def logo_upload_to(instance, filename):
    return f"campings/{instance.pk or 'new'}/logo/{filename}"


def photo_upload_to(instance, filename):
    return f"campings/{instance.camping_id}/photos/{filename}"


def unique_slug(value, model, exclude_pk=None, max_length=55):
    base = slugify(value).replace("_", "-")[:max_length].strip("-") or "camping"
    if base in RESERVED_SLUGS:
        base = f"{base}-camping"
    slug, n = base, 2
    queryset = model.objects.all()
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    while queryset.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Camping(models.Model):
    name = models.CharField(_("name"), max_length=150)
    slug = models.SlugField(
        _("web address"),
        max_length=80,
        unique=True,
        validators=[slug_validator],
        help_text=_("Part of the address of your public page. Lowercase letters, numbers and hyphens."),
    )
    tagline = TranslatedField(_("tagline"), max_chars=180, help_text=_("A short sentence shown under the name."))
    description = TranslatedField(_("description"), textarea=True)
    location_info = TranslatedField(
        _("location and how to get there"),
        textarea=True,
        help_text=_("Surroundings, distances, directions, public transport..."),
    )
    stars = models.PositiveSmallIntegerField(
        _("category (stars)"), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    # Contact
    email = models.EmailField(_("e-mail"), blank=True)
    phone = models.CharField(_("phone"), max_length=40, blank=True)
    whatsapp = models.CharField(
        _("WhatsApp"), max_length=40, blank=True, help_text=_("International format, e.g. +34600111222.")
    )
    website = models.URLField(_("website"), blank=True)
    instagram = models.URLField(_("Instagram"), blank=True)
    facebook = models.URLField(_("Facebook"), blank=True)

    # Location
    address = models.CharField(_("address"), max_length=255, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=20, blank=True)
    city = models.CharField(_("town / city"), max_length=100, blank=True)
    region = models.CharField(_("region / province"), max_length=100, blank=True)
    country = models.CharField(_("country"), max_length=100, blank=True)
    latitude = models.DecimalField(
        _("latitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        _("longitude"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )

    # Opening period
    open_all_year = models.BooleanField(_("open all year"), default=False)
    opening_date = models.DateField(
        _("opening date"), null=True, blank=True, help_text=_("Only the day and month are used: it repeats every year.")
    )
    closing_date = models.DateField(
        _("closing date"), null=True, blank=True, help_text=_("Last day of departure. It repeats every year.")
    )

    # Languages & money
    default_language = models.CharField(
        _("main language"), max_length=10, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE
    )
    languages = models.JSONField(_("content languages"), default=default_languages, blank=True)
    currency = models.CharField(_("currency"), max_length=3, choices=catalog.CURRENCIES, default="EUR")

    # Appearance
    primary_color = models.CharField(
        _("main colour"), max_length=7, default="#2f6f4e", validators=[hex_color_validator]
    )
    accent_color = models.CharField(
        _("accent colour"), max_length=7, default="#e9a23b", validators=[hex_color_validator]
    )
    font_style = models.CharField(_("typography"), max_length=20, choices=catalog.FONT_STYLES, default="modern")
    logo = models.ImageField(_("logo"), upload_to=logo_upload_to, blank=True)

    # Bookings
    accepts_booking_requests = models.BooleanField(_("accept booking requests"), default=True)
    notification_email = models.EmailField(
        _("e-mail for booking requests"),
        blank=True,
        help_text=_("Where new booking requests are notified. Defaults to the contact e-mail."),
    )

    # Publication
    is_published = models.BooleanField(_("published"), default=False)
    is_approved = models.BooleanField(
        _("approved by the platform"),
        default=True,
        help_text=_("Only approved campings can be seen by the public."),
    )
    custom_domain = models.CharField(
        _("own domain"),
        max_length=253,
        blank=True,
        null=True,
        unique=True,
        validators=[domain_validator],
        help_text=_("Optional, e.g. www.mycamping.com. Point its DNS to the platform first."),
    )
    # Set on the first secure visit through ``custom_domain``: from then on
    # links and the platform address lead to the camping's own domain.
    domain_verified_at = models.DateTimeField(_("domain working since"), null=True, blank=True, editable=False)
    show_platform_credit = models.BooleanField(
        _("show the platform credit"),
        default=True,
        help_text=_("“Powered by” link in the footer of the camping's website."),
    )

    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("camping")
        verbose_name_plural = _("campings")

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        if self.slug in RESERVED_SLUGS:
            errors["slug"] = _("This address is reserved, please choose another one.")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self.name, Camping, exclude_pk=self.pk)
        self.custom_domain = (self.custom_domain or "").strip().lower() or None
        valid = platform_language_codes()
        if self.default_language not in valid:
            self.default_language = settings.LANGUAGE_CODE
        languages = [code for code in (self.languages or []) if code in valid and code != self.default_language]
        self.languages = [self.default_language, *dict.fromkeys(languages)]
        super().save(*args, **kwargs)

    # --- helpers -------------------------------------------------------------

    def get_absolute_url(self):
        return reverse("public:camping_detail", kwargs={"slug": self.slug})

    @property
    def site_host(self):
        """Host of the camping's own website, or "" if it lives on the platform."""
        if self.custom_domain and self.domain_verified_at:
            return self.custom_domain
        if settings.CAMPING_DOMAIN_SUFFIX:
            return f"{self.slug}.{settings.CAMPING_DOMAIN_SUFFIX}"
        return ""

    @property
    def site_url(self):
        """``https://host`` of the camping's own website (no trailing slash) or ""."""
        host = self.site_host
        return f"{settings.CAMPING_URL_SCHEME}://{host}" if host else ""

    @property
    def domain_pending(self):
        """The own domain is configured but no visit has arrived through it yet."""
        return bool(self.custom_domain and not self.domain_verified_at)

    def t(self, field_name):
        """Translated value of a TranslatedField in the active language."""
        return translate_value(getattr(self, field_name), fallback=self.default_language)

    @property
    def is_public(self):
        return self.is_published and self.is_approved

    @property
    def content_languages(self):
        valid = platform_language_codes()
        ordered = [self.default_language, *[c for c in (self.languages or []) if c != self.default_language]]
        return [code for code in dict.fromkeys(ordered) if code in valid]

    @property
    def booking_email(self):
        return self.notification_email or self.email

    @property
    def location_label(self):
        return ", ".join(part for part in (self.city, self.region) if part)

    @property
    def cover_photo(self):
        photos = getattr(self, "_prefetched_objects_cache", {}).get("photos")
        if photos is not None:
            return photos[0] if photos else None
        return self.photos.first()

    def map_links(self):
        """Embeddable OpenStreetMap view and directions links, if located."""
        if self.latitude is not None and self.longitude is not None:
            lat, lon = float(self.latitude), float(self.longitude)
            return {
                "embed": (
                    "https://www.openstreetmap.org/export/embed.html?bbox="
                    f"{lon - 0.02:.5f}%2C{lat - 0.012:.5f}%2C{lon + 0.02:.5f}%2C{lat + 0.012:.5f}"
                    f"&layer=mapnik&marker={lat:.6f}%2C{lon:.6f}"
                ),
                "link": f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=15/{lat:.6f}/{lon:.6f}",
                "directions": f"https://www.google.com/maps/dir/?api=1&destination={lat:.6f},{lon:.6f}",
            }
        parts = [self.address, self.postal_code, self.city, self.region, self.country]
        query = ", ".join(part for part in parts if part)
        if query:
            return {"directions": f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"}
        return None

    def is_open_on(self, night):
        """Whether guests can stay the night of ``night``.

        The opening period repeats every year: only day and month count. The
        closing date is the last departure day, so its night is closed.
        """
        if self.open_all_year or not (self.opening_date and self.closing_date):
            return True
        start = (self.opening_date.month, self.opening_date.day)
        end = (self.closing_date.month, self.closing_date.day)
        current = (night.month, night.day)
        if start == end:
            return True
        if start < end:
            return start <= current < end
        return current >= start or current < end  # e.g. open December to April

    def get_policy(self):
        policy = getattr(self, "_policy_cache", None)
        if policy is None:
            try:
                policy = self.policy
            except BookingPolicy.DoesNotExist:
                policy, _created = BookingPolicy.objects.get_or_create(camping=self)
            self._policy_cache = policy
        return policy

    def starting_price(self):
        """Cheapest nightly price among visible accommodations (any season)."""
        prices = []
        for accommodation in self.accommodations.all():
            if not accommodation.is_active:
                continue
            prices.append(accommodation.base_price)
            prices.extend(rate.price for rate in accommodation.rates.all())
        prices = [p for p in prices if p and p > 0]
        return min(prices) if prices else None


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        STAFF = "staff", _("Staff")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(_("role"), max_length=10, choices=Role.choices, default=Role.OWNER)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        verbose_name = _("member")
        verbose_name_plural = _("members")
        constraints = [models.UniqueConstraint(fields=["user", "camping"], name="unique_membership")]
        ordering = ["camping", "user__email"]

    def __str__(self):
        return f"{self.user} @ {self.camping} ({self.get_role_display()})"

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER


class Season(models.Model):
    """A rate: low, mid or high season, or a special period (Easter, bank holidays, events).

    Its prices apply on the dates of its periods, which may repeat several
    times a year (e.g. high season in summer and at Christmas). Where a special
    period overlaps a regular season, the special period wins.
    """

    class Kind(models.TextChoices):
        LOW = "low", _("Low season")
        MID = "mid", _("Mid season")
        HIGH = "high", _("High season")
        SPECIAL = "special", _("Special period")

    KIND_COLORS = {"low": "#3f8f6b", "mid": "#d69a2d", "high": "#d4553a", "special": "#7c5cbf"}

    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="seasons")
    name = TranslatedField(_("name"), max_chars=60)
    kind = models.CharField(_("type"), max_length=10, choices=Kind.choices, default=Kind.MID)
    min_nights = models.PositiveSmallIntegerField(
        _("minimum nights"),
        null=True,
        blank=True,
        help_text=_("Optional minimum stay for arrivals in this season."),
    )
    color = models.CharField(_("colour"), max_length=7, default="#3f8f6b", validators=[hex_color_validator])

    class Meta:
        ordering = [
            models.Case(
                models.When(kind="low", then=models.Value(0)),
                models.When(kind="mid", then=models.Value(1)),
                models.When(kind="high", then=models.Value(2)),
                default=models.Value(3),
            ),
            "id",
        ]
        verbose_name = _("season")
        verbose_name_plural = _("seasons")

    def __str__(self):
        return translate_value(self.name) or f"#{self.pk}"

    @property
    def is_special(self):
        return self.kind == self.Kind.SPECIAL

    def contains(self, day):
        return any(period.start_date <= day <= period.end_date for period in self.periods.all())

    def upcoming_periods(self, today):
        """Periods that have not ended yet (uses the prefetched ``periods``)."""
        return [period for period in self.periods.all() if period.end_date >= today]


class SeasonPeriod(models.Model):
    """Dates on which a season applies (both days included)."""

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="periods", verbose_name=_("season"))
    start_date = models.DateField(_("from"))
    end_date = models.DateField(_("to (inclusive)"))

    class Meta:
        ordering = ["start_date"]
        verbose_name = _("period")
        verbose_name_plural = _("periods")

    def __str__(self):
        return f"{self.start_date:%d/%m/%Y} – {self.end_date:%d/%m/%Y}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": _("The end date must be on or after the start date.")})

    def overlaps(self, start, end):
        return self.start_date <= end and start <= self.end_date


class AccommodationType(models.Model):
    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="accommodations")
    kind = models.CharField(_("type"), max_length=20, choices=catalog.ACCOMMODATION_KIND_CHOICES, default="pitch")
    name = TranslatedField(_("name"), max_chars=120)
    description = TranslatedField(_("description"), textarea=True)
    max_guests = models.PositiveSmallIntegerField(
        _("maximum guests"), default=4, validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    size_m2 = models.PositiveIntegerField(_("size (m²)"), null=True, blank=True)
    bedrooms = models.PositiveSmallIntegerField(_("bedrooms"), null=True, blank=True)
    units = models.PositiveSmallIntegerField(
        _("units available"),
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_("How many of these you have. Used to check availability."),
    )
    amenities = models.JSONField(_("amenities"), default=list, blank=True)
    base_price = models.DecimalField(
        _("base price"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("0"),
        validators=NON_NEGATIVE,
        help_text=_("Used when no seasonal price is defined."),
    )
    price_unit = models.CharField(
        _("price applies"), max_length=20, choices=catalog.ACCOMMODATION_PRICE_UNITS, default="night"
    )
    min_nights = models.PositiveSmallIntegerField(_("minimum nights"), null=True, blank=True)
    is_active = models.BooleanField(_("visible"), default=True)
    position = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("accommodation type")
        verbose_name_plural = _("accommodation types")

    def __str__(self):
        return translate_value(self.name) or self.get_kind_display()

    @property
    def display_name(self):
        return translate_value(self.name, fallback=self.camping.default_language) or str(self.get_kind_display())

    @property
    def kind_icon(self):
        return catalog.ACCOMMODATION_KIND_ICONS.get(self.kind, "house")

    @property
    def amenity_items(self):
        return [
            {"key": key, "label": catalog.AMENITY_MAP[key]["label"], "icon": catalog.AMENITY_MAP[key]["icon"]}
            for key in (self.amenities or [])
            if key in catalog.AMENITY_MAP
        ]

    def rate_map(self):
        return {rate.season_id: rate.price for rate in self.rates.all()}

    def price_for(self, season, rates=None):
        if season is None:
            return self.base_price
        rates = self.rate_map() if rates is None else rates
        return rates.get(season.pk, self.base_price)

    def lowest_price(self):
        prices = [self.base_price, *self.rate_map().values()]
        prices = [p for p in prices if p and p > 0]
        return min(prices) if prices else None


class AccommodationRate(models.Model):
    accommodation = models.ForeignKey(AccommodationType, on_delete=models.CASCADE, related_name="rates")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="accommodation_rates")
    price = models.DecimalField(_("price"), max_digits=8, decimal_places=2, validators=NON_NEGATIVE)

    class Meta:
        verbose_name = _("seasonal price")
        verbose_name_plural = _("seasonal prices")
        constraints = [models.UniqueConstraint(fields=["accommodation", "season"], name="unique_accommodation_rate")]

    def __str__(self):
        return f"{self.accommodation} · {self.season}: {self.price}"


class Service(models.Model):
    """Priced item: people, vehicles, electricity, pets, extras, taxes..."""

    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="services")
    name = TranslatedField(_("name"), max_chars=100)
    description = TranslatedField(_("description"), max_chars=300)
    icon = models.CharField(_("icon"), max_length=30, choices=catalog.SERVICE_ICONS, default="tag")
    price = models.DecimalField(
        _("base price"), max_digits=8, decimal_places=2, default=Decimal("0"), validators=NON_NEGATIVE
    )
    unit = models.CharField(_("price unit"), max_length=20, choices=catalog.SERVICE_UNITS, default="night")
    mode = models.CharField(_("how it is charged"), max_length=20, choices=catalog.SERVICE_MODES, default="optional")
    accommodations = models.ManyToManyField(
        AccommodationType,
        blank=True,
        related_name="services",
        verbose_name=_("applies to"),
        help_text=_("Leave empty to apply it to every accommodation type."),
    )
    is_active = models.BooleanField(_("visible"), default=True)
    position = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("service")
        verbose_name_plural = _("services and extras")

    def __str__(self):
        return translate_value(self.name) or f"#{self.pk}"

    @property
    def display_name(self):
        return translate_value(self.name, fallback=self.camping.default_language)

    def rate_map(self):
        return {rate.season_id: rate.price for rate in self.rates.all()}

    def price_for(self, season, rates=None):
        if season is None:
            return self.price
        rates = self.rate_map() if rates is None else rates
        return rates.get(season.pk, self.price)

    def applies_to(self, accommodation):
        ids = [a.pk for a in self.accommodations.all()]
        return not ids or (accommodation is not None and accommodation.pk in ids)


class ServiceRate(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="rates")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="service_rates")
    price = models.DecimalField(_("price"), max_digits=8, decimal_places=2, validators=NON_NEGATIVE)

    class Meta:
        verbose_name = _("seasonal service price")
        verbose_name_plural = _("seasonal service prices")
        constraints = [models.UniqueConstraint(fields=["service", "season"], name="unique_service_rate")]

    def __str__(self):
        return f"{self.service} · {self.season}: {self.price}"


class Facility(models.Model):
    CUSTOM = "custom"

    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="facilities")
    kind = models.CharField(
        _("facility"),
        max_length=40,
        choices=[(key, label) for key, label, _icon, _group in catalog.FACILITIES] + [(CUSTOM, _("Custom"))],
    )
    name = TranslatedField(_("name"), max_chars=100)
    description = TranslatedField(_("details"), max_chars=300, help_text=_("Opening hours, season, conditions..."))
    icon = models.CharField(_("icon"), max_length=40, blank=True, choices=catalog.CUSTOM_FACILITY_ICONS)
    is_paid = models.BooleanField(_("extra charge"), default=False)
    position = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("facility")
        verbose_name_plural = _("facilities")
        constraints = [
            models.UniqueConstraint(
                fields=["camping", "kind"], condition=~Q(kind="custom"), name="unique_facility_kind"
            )
        ]

    def __str__(self):
        return str(self.display_name)

    @property
    def catalog_entry(self):
        return catalog.FACILITY_MAP.get(self.kind)

    @property
    def display_name(self):
        custom = translate_value(self.name)
        if custom:
            return custom
        entry = self.catalog_entry
        return entry["label"] if entry else _("Facility")

    @property
    def icon_name(self):
        if self.icon:
            return self.icon
        entry = self.catalog_entry
        return entry["icon"] if entry else "sparkles"

    @property
    def group(self):
        entry = self.catalog_entry
        return entry["group"] if entry else "other"


class Photo(models.Model):
    camping = models.ForeignKey(Camping, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(_("image"), upload_to=photo_upload_to)
    thumbnail = models.ImageField(_("thumbnail"), upload_to=photo_upload_to)
    width = models.PositiveIntegerField(default=0, editable=False)
    height = models.PositiveIntegerField(default=0, editable=False)
    caption = TranslatedField(_("caption"), max_chars=200)
    accommodation = models.ForeignKey(
        AccommodationType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="photos",
        verbose_name=_("accommodation"),
        help_text=_("Show this photo on an accommodation type as well."),
    )
    position = models.PositiveIntegerField(_("order"), default=0)
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("photo")
        verbose_name_plural = _("photos")

    def __str__(self):
        return translate_value(self.caption) or self.image.name

    @property
    def alt_text(self):
        return translate_value(self.caption) or self.camping.name


class BookingPolicy(models.Model):
    camping = models.OneToOneField(Camping, on_delete=models.CASCADE, related_name="policy")
    check_in_from = models.TimeField(_("check-in from"), default=time(14, 0))
    check_in_until = models.TimeField(_("check-in until"), null=True, blank=True, default=time(21, 0))
    check_out_until = models.TimeField(_("check-out until"), default=time(12, 0))
    min_nights = models.PositiveSmallIntegerField(_("minimum nights"), default=1, validators=[MinValueValidator(1)])
    max_nights = models.PositiveSmallIntegerField(_("maximum nights"), null=True, blank=True)
    min_age = models.PositiveSmallIntegerField(_("minimum age of the person booking"), default=18)
    deposit_percent = models.PositiveSmallIntegerField(
        _("deposit to confirm (%)"),
        default=0,
        validators=PERCENT,
        help_text=_("Percentage of the total requested to confirm a booking. 0 = no deposit."),
    )
    refundable = models.BooleanField(_("cancellations allowed"), default=True)
    free_cancellation_days = models.PositiveSmallIntegerField(
        _("free cancellation until (days before arrival)"), default=7
    )
    cancellation_fee_percent = models.PositiveSmallIntegerField(
        _("fee for later cancellations (%)"), default=100, validators=PERCENT
    )
    pets_allowed = models.BooleanField(_("pets allowed"), default=True)
    quiet_hours_from = models.TimeField(_("quiet hours from"), null=True, blank=True, default=time(23, 0))
    quiet_hours_until = models.TimeField(_("quiet hours until"), null=True, blank=True, default=time(8, 0))
    payment_methods = models.JSONField(_("payment methods"), default=list, blank=True)
    cancellation_text = TranslatedField(_("cancellation details"), textarea=True)
    payment_text = TranslatedField(_("payment details"), textarea=True)
    pets_text = TranslatedField(_("pet policy"), textarea=True)
    rules_text = TranslatedField(_("camping rules"), textarea=True)

    class Meta:
        verbose_name = _("booking policy")
        verbose_name_plural = _("booking policies")

    def __str__(self):
        return str(_("Booking policy of %(camping)s") % {"camping": self.camping})

    def clean(self):
        if self.max_nights and self.min_nights and self.max_nights < self.min_nights:
            raise ValidationError({"max_nights": _("The maximum stay cannot be shorter than the minimum stay.")})

    @property
    def payment_method_labels(self):
        return [
            catalog.PAYMENT_METHOD_MAP[key] for key in (self.payment_methods or []) if key in catalog.PAYMENT_METHOD_MAP
        ]
