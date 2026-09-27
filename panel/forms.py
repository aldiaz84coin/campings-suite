import json

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.utils.translation import gettext_lazy as _

from campings import catalog
from campings.models import (
    AccommodationType,
    BookingPolicy,
    Camping,
    Facility,
    Membership,
    Photo,
    Season,
    SeasonPeriod,
    Service,
    domain_validator,
)
from core.fields import TranslatedFormMixin

User = get_user_model()


class DomainField(forms.CharField):
    """Accepts what people paste (``https://WWW.Camping.com/``) and keeps ``www.camping.com``."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 253)
        kwargs.setdefault("required", False)
        kwargs.setdefault("empty_value", None)
        kwargs.setdefault("validators", [domain_validator])
        super().__init__(**kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return value
        value = value.strip().lower()
        for prefix in ("https://", "http://"):
            value = value.removeprefix(prefix)
        return value.split("/", 1)[0] or None


DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TIME_WIDGET = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
COLOR_WIDGET = forms.TextInput(attrs={"type": "color"})


class CampingContentForm(TranslatedFormMixin, forms.ModelForm):
    """Model form whose translated fields follow the camping's languages."""

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, **kwargs)
        self.camping = camping
        self.setup_translated_fields(camping.content_languages, camping.default_language)
        if "position" in self.fields:
            self.fields["position"].required = False
            self.fields["position"].help_text = _("Lower numbers are shown first.")

    def clean_position(self):
        return self.cleaned_data.get("position") or 0


# --- Auth ----------------------------------------------------------------------


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label=_("E-mail"), widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"})
    )


class PanelPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        # Invited users have no password yet and must be able to set one.
        return User._default_manager.filter(email__iexact=email, is_active=True)


class SignupForm(forms.Form):
    camping_name = forms.CharField(label=_("Name of your camping"), max_length=150)
    first_name = forms.CharField(label=_("Your name"), max_length=150)
    email = forms.EmailField(label=_("E-mail"), widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Repeat the password"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    accept_terms = forms.BooleanField(label=_("I accept the terms of use and the privacy policy."))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("There is already an account with this e-mail. Please sign in."))
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("The two passwords do not match."))
        if p1:
            user = User(email=cleaned.get("email") or "", first_name=cleaned.get("first_name") or "")
            try:
                password_validation.validate_password(p1, user)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned


class AccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "preferred_language"]
        help_texts = {"preferred_language": _("Language of the panel when you sign in.")}


# --- Camping ---------------------------------------------------------------------


class ProfileForm(CampingContentForm):
    class Meta:
        model = Camping
        fields = [
            "name",
            "tagline",
            "description",
            "stars",
            "email",
            "phone",
            "whatsapp",
            "website",
            "instagram",
            "facebook",
        ]
        widgets = {"stars": forms.Select(choices=[("", "—")] + [(i, "★" * i) for i in range(1, 6)])}


class LocationForm(CampingContentForm):
    class Meta:
        model = Camping
        fields = [
            "address",
            "postal_code",
            "city",
            "region",
            "country",
            "latitude",
            "longitude",
            "location_info",
            "open_all_year",
            "opening_date",
            "closing_date",
        ]
        widgets = {
            "opening_date": DATE_WIDGET,
            "closing_date": DATE_WIDGET,
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "placeholder": "41.387015"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "placeholder": "2.170047"}),
        }
        help_texts = {
            "latitude": _("Tip: in Google Maps, right-click on your camping and click the coordinates to copy them."),
        }

    def clean(self):
        cleaned = super().clean()
        opening, closing = cleaned.get("opening_date"), cleaned.get("closing_date")
        if not cleaned.get("open_all_year"):
            if bool(opening) != bool(closing):
                self.add_error("closing_date", _("Fill in both dates, or tick “open all year”."))
            elif opening and closing and (opening.month, opening.day) == (closing.month, closing.day):
                self.add_error("closing_date", _("The closing date must be different from the opening date."))
        return cleaned


class SettingsForm(forms.ModelForm):
    custom_domain = DomainField(label=_("Own domain"), help_text=Camping._meta.get_field("custom_domain").help_text)
    languages = forms.MultipleChoiceField(
        label=_("Languages of your page"),
        choices=settings.LANGUAGES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("You will be able to write your texts in each of these languages."),
    )

    class Meta:
        model = Camping
        fields = [
            "slug",
            "default_language",
            "languages",
            "currency",
            "accepts_booking_requests",
            "notification_email",
            "custom_domain",
            "show_platform_credit",
        ]

    def __init__(self, *args, allow_domain=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not allow_domain:
            # Own domain and white label are managed by the platform administrators.
            del self.fields["custom_domain"]
            del self.fields["show_platform_credit"]

    def clean_slug(self):
        return self.cleaned_data["slug"].strip().lower()

    def clean(self):
        cleaned = super().clean()
        default = cleaned.get("default_language")
        languages = list(cleaned.get("languages") or [])
        if default and default not in languages:
            languages.insert(0, default)
        cleaned["languages"] = languages
        return cleaned


class AppearanceForm(forms.ModelForm):
    logo_file = forms.FileField(
        label=_("Logo"),
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
        help_text=_("PNG with transparent background works best."),
    )
    remove_logo = forms.BooleanField(label=_("Remove the current logo"), required=False)

    class Meta:
        model = Camping
        fields = ["primary_color", "accent_color", "font_style"]
        widgets = {
            "primary_color": COLOR_WIDGET,
            "accent_color": COLOR_WIDGET,
            "font_style": forms.RadioSelect,
        }


# --- Photos ---------------------------------------------------------------------


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*", "multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(item, initial) for item in data]
        return [single(data, initial)]


class PhotoUploadForm(forms.Form):
    images = MultipleImageField(label=_("Photos"))


class PhotoForm(CampingContentForm):
    class Meta:
        model = Photo
        fields = ["caption", "accommodation"]

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, camping=camping, **kwargs)
        self.fields["accommodation"].queryset = camping.accommodations.all()
        self.fields["accommodation"].label_from_instance = lambda obj: obj.display_name
        self.fields["accommodation"].empty_label = _("— Only in the general gallery —")


# --- Offer ------------------------------------------------------------------------


class FacilityForm(CampingContentForm):
    class Meta:
        model = Facility
        fields = ["name", "description", "icon", "is_paid"]

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, camping=camping, **kwargs)
        is_custom = not self.instance.pk or self.instance.kind == Facility.CUSTOM
        if is_custom:
            self.fields["name"].required = True
        else:
            self.fields["name"].help_text = _("Optional: leave empty to use the standard name “%(name)s”.") % {
                "name": self.instance.catalog_entry["label"]
            }
            del self.fields["icon"]


class PhotoChoiceField(forms.ModelMultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def label_from_instance(self, obj):
        return obj.pk


class AccommodationForm(CampingContentForm):
    amenities = forms.MultipleChoiceField(
        label=_("Amenities"), choices=catalog.AMENITY_CHOICES, widget=forms.CheckboxSelectMultiple, required=False
    )
    photos = PhotoChoiceField(queryset=Photo.objects.none(), required=False, label=_("Photos"))

    class Meta:
        model = AccommodationType
        fields = [
            "kind",
            "name",
            "description",
            "max_guests",
            "size_m2",
            "bedrooms",
            "units",
            "amenities",
            "base_price",
            "price_unit",
            "min_nights",
            "is_active",
            "position",
        ]
        widgets = {"base_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"})}

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, camping=camping, **kwargs)
        self.fields["name"].required = True
        self.fields["photos"].queryset = camping.photos.all()
        if self.instance.pk:
            self.fields["photos"].initial = list(self.instance.photos.values_list("pk", flat=True))

    def save(self, commit=True):
        accommodation = super().save(commit=commit)
        if commit:
            self.save_photos(accommodation)
        return accommodation

    def save_photos(self, accommodation):
        selected = {photo.pk for photo in self.cleaned_data.get("photos") or []}
        self.camping.photos.filter(accommodation=accommodation).exclude(pk__in=selected).update(accommodation=None)
        self.camping.photos.filter(pk__in=selected).update(accommodation=accommodation)


class ServiceForm(CampingContentForm):
    accommodations = forms.ModelMultipleChoiceField(
        queryset=AccommodationType.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Applies to"),
        help_text=_("Leave empty to apply it to every accommodation type."),
    )

    class Meta:
        model = Service
        fields = ["name", "description", "icon", "price", "unit", "mode", "accommodations", "is_active", "position"]
        widgets = {"price": forms.NumberInput(attrs={"step": "0.01", "min": "0"})}

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, camping=camping, **kwargs)
        self.fields["name"].required = True
        self.fields["accommodations"].queryset = camping.accommodations.all()
        self.fields["accommodations"].label_from_instance = lambda obj: obj.display_name


class SeasonForm(CampingContentForm):
    class Meta:
        model = Season
        fields = ["name", "kind", "min_nights", "color"]
        widgets = {"color": COLOR_WIDGET}

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, camping=camping, **kwargs)
        self.fields["name"].required = True
        self.fields["kind"].widget.attrs["data-season-kind"] = ""
        self.fields["color"].widget.attrs["data-kind-colors"] = json.dumps(Season.KIND_COLORS)
        if not self.instance.pk:
            kind = self.initial.get("kind") or self.instance.kind
            self.initial.setdefault("color", Season.KIND_COLORS.get(kind, Season.KIND_COLORS["mid"]))


class SeasonPeriodForm(forms.ModelForm):
    class Meta:
        model = SeasonPeriod
        fields = ["start_date", "end_date"]
        widgets = {"start_date": DATE_WIDGET, "end_date": DATE_WIDGET}


class BaseSeasonPeriodFormSet(forms.BaseInlineFormSet):
    """Periods of one season: they cannot overlap each other."""

    def clean(self):
        super().clean()
        self.ranges = []
        if any(self.errors):
            return
        for form in self.forms:
            data = getattr(form, "cleaned_data", None) or {}
            start, end = data.get("start_date"), data.get("end_date")
            if data.get("DELETE") or not start or not end:
                continue
            if any(start <= other_end and other_start <= end for other_start, other_end in self.ranges):
                raise forms.ValidationError(_("The periods of a season cannot overlap each other."))
            self.ranges.append((start, end))


SeasonPeriodFormSet = forms.inlineformset_factory(
    Season,
    SeasonPeriod,
    form=SeasonPeriodForm,
    formset=BaseSeasonPeriodFormSet,
    extra=1,
    can_delete=True,
)


class PolicyForm(CampingContentForm):
    payment_methods = forms.MultipleChoiceField(
        label=_("Accepted payment methods"),
        choices=catalog.PAYMENT_METHODS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = BookingPolicy
        fields = [
            "check_in_from",
            "check_in_until",
            "check_out_until",
            "quiet_hours_from",
            "quiet_hours_until",
            "min_nights",
            "max_nights",
            "min_age",
            "deposit_percent",
            "payment_methods",
            "payment_text",
            "refundable",
            "free_cancellation_days",
            "cancellation_fee_percent",
            "cancellation_text",
            "pets_allowed",
            "pets_text",
            "rules_text",
        ]
        widgets = {
            "check_in_from": TIME_WIDGET,
            "check_in_until": TIME_WIDGET,
            "check_out_until": TIME_WIDGET,
            "quiet_hours_from": TIME_WIDGET,
            "quiet_hours_until": TIME_WIDGET,
        }


# --- Team & platform -------------------------------------------------------------


class InviteForm(forms.Form):
    email = forms.EmailField(label=_("E-mail"))
    role = forms.ChoiceField(label=_("Role"), choices=Membership.Role.choices, initial=Membership.Role.STAFF)

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, **kwargs)
        self.camping = camping

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Membership.objects.filter(camping=self.camping, user__email__iexact=email).exists():
            raise forms.ValidationError(_("This person is already a member of the team."))
        return email


class PlatformCampingForm(forms.Form):
    name = forms.CharField(label=_("Camping name"), max_length=150)
    owner_email = forms.EmailField(label=_("Owner's e-mail"))
    owner_name = forms.CharField(label=_("Owner's name"), max_length=150, required=False)
    default_language = forms.ChoiceField(label=_("Main language"), choices=settings.LANGUAGES)
    custom_domain = DomainField(
        label=_("Own domain"),
        help_text=_("Optional, e.g. www.mycamping.com. You can also add it later in the camping's settings."),
    )

    def clean_custom_domain(self):
        domain = self.cleaned_data.get("custom_domain")
        if domain and Camping.objects.filter(custom_domain=domain).exists():
            raise forms.ValidationError(_("Another camping already uses this domain."))
        return domain
