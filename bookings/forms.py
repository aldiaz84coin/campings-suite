from datetime import timedelta

from django import forms
from django.utils import timezone, translation
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from campings.pricing import build_quote
from core.formatting import format_money

from .models import BookingRequest

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class AccommodationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name


class ExtrasField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        price = format_money(obj.price, obj.camping.currency)
        return f"{obj.display_name} · {price} {obj.get_unit_display()}"


class StayFieldsMixin:
    """Shared set-up for forms that describe a stay at ``camping``."""

    def setup_stay_fields(self, camping):
        self.camping = camping
        self.policy = camping.get_policy()
        accommodations = camping.accommodations.filter(is_active=True)
        self.fields["accommodation"].queryset = accommodations
        self.fields["accommodation"].empty_label = None if accommodations.count() == 1 else _("Choose…")
        if not self.policy.pets_allowed and "pets" in self.fields:
            del self.fields["pets"]


class BookingRequestForm(StayFieldsMixin, forms.ModelForm):
    accommodation = AccommodationChoiceField(queryset=None, label=_("Accommodation"))
    extras = ExtrasField(queryset=None, required=False, widget=forms.CheckboxSelectMultiple, label=_("Extras"))
    adults = forms.IntegerField(label=_("Adults"), min_value=1, max_value=30, initial=2)
    children = forms.IntegerField(label=_("Children"), min_value=0, max_value=30, initial=0, required=False)
    pets = forms.IntegerField(label=_("Pets"), min_value=0, max_value=10, initial=0, required=False)
    accept_privacy = forms.BooleanField(
        label=_("I agree that the camping uses my data to answer this request."), required=True
    )
    # Honeypot: humans never see it, bots tend to fill it in.
    website = forms.CharField(required=False, label=_("Leave this field empty"))

    class Meta:
        model = BookingRequest
        fields = [
            "accommodation",
            "arrival",
            "departure",
            "adults",
            "children",
            "pets",
            "extras",
            "name",
            "email",
            "phone",
            "country",
            "message",
        ]
        widgets = {
            "arrival": DATE_WIDGET,
            "departure": DATE_WIDGET,
            "message": forms.Textarea(attrs={"rows": 4}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
            "country": forms.TextInput(attrs={"autocomplete": "country-name"}),
        }

    def __init__(self, camping, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.camping = camping
        self.setup_stay_fields(camping)
        self.fields["extras"].queryset = camping.services.filter(is_active=True, mode="optional").prefetch_related(
            "accommodations"
        )
        self.fields["website"].widget.attrs.update({"autocomplete": "off", "tabindex": "-1"})
        today = timezone.localdate()
        self.fields["arrival"].widget.attrs["min"] = today.isoformat()
        self.fields["departure"].widget.attrs["min"] = (today + timedelta(days=1)).isoformat()
        self.quote = None

    def clean_children(self):
        return self.cleaned_data.get("children") or 0

    def clean_pets(self):
        return self.cleaned_data.get("pets") or 0

    @property
    def is_spam(self):
        return bool(self.cleaned_data.get("website"))

    def _build_quote(self):
        cleaned = self.cleaned_data
        return build_quote(
            self.camping,
            cleaned["accommodation"],
            cleaned["arrival"],
            cleaned["departure"],
            adults=cleaned.get("adults") or 0,
            children=cleaned.get("children") or 0,
            pets=cleaned.get("pets") or 0,
            extras=list(cleaned.get("extras") or []),
        )

    def clean(self):
        cleaned = super().clean()
        required = ("accommodation", "arrival", "departure", "adults")
        if all(cleaned.get(name) is not None for name in required) and not self.errors:
            self.quote = self._build_quote()
            for error in self.quote.errors:
                self.add_error(None, error)
        return cleaned

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.camping = self.camping
        booking.language = get_language() or booking.language
        if self.quote is not None:
            quotes = {booking.language: self.quote.as_dict()}
            with translation.override(self.camping.default_language):
                quotes.setdefault(self.camping.default_language, self._build_quote().as_dict())
            booking.quote = quotes
            booking.estimated_total = self.quote.total
        if commit:
            booking.save()
            self.save_m2m()
        return booking


class StaySearchForm(StayFieldsMixin, forms.Form):
    """Compact GET form on the camping page that leads to the booking page."""

    accommodation = AccommodationChoiceField(queryset=None, label=_("Accommodation"), required=False)
    arrival = forms.DateField(label=_("Arrival"), required=False, widget=DATE_WIDGET)
    departure = forms.DateField(label=_("Departure"), required=False, widget=DATE_WIDGET)
    adults = forms.IntegerField(label=_("Adults"), min_value=1, max_value=30, initial=2, required=False)
    children = forms.IntegerField(label=_("Children"), min_value=0, max_value=30, initial=0, required=False)

    def __init__(self, camping, *args, **kwargs):
        kwargs.setdefault("auto_id", "search_%s")
        super().__init__(*args, **kwargs)
        self.setup_stay_fields(camping)
        today = timezone.localdate()
        self.fields["arrival"].widget.attrs["min"] = today.isoformat()
        self.fields["departure"].widget.attrs["min"] = (today + timedelta(days=1)).isoformat()


class QuoteForm(StayFieldsMixin, forms.Form):
    """Parameters accepted by the JSON quote endpoint."""

    accommodation = AccommodationChoiceField(queryset=None)
    arrival = forms.DateField()
    departure = forms.DateField()
    adults = forms.IntegerField(min_value=0, max_value=30, required=False)
    children = forms.IntegerField(min_value=0, max_value=30, required=False)
    pets = forms.IntegerField(min_value=0, max_value=10, required=False)
    extras = forms.ModelMultipleChoiceField(queryset=None, required=False)

    def __init__(self, camping, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_stay_fields(camping)
        self.fields["extras"].queryset = camping.services.filter(is_active=True, mode="optional")

    def quote(self):
        data = self.cleaned_data
        return build_quote(
            self.camping,
            data["accommodation"],
            data["arrival"],
            data["departure"],
            adults=data.get("adults") if data.get("adults") is not None else 2,
            children=data.get("children") or 0,
            pets=data.get("pets") or 0,
            extras=list(data.get("extras") or []),
        )


class BookingStatusForm(forms.ModelForm):
    notify_guest = forms.BooleanField(
        label=_("Send an e-mail to the guest about this change"), required=False, initial=True
    )

    class Meta:
        model = BookingRequest
        fields = ["status", "internal_notes"]
        widgets = {"internal_notes": forms.Textarea(attrs={"rows": 4})}
