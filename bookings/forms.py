from datetime import timedelta
from decimal import Decimal

from django import forms
from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from campings.pricing import available_units, build_quote
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
        self.fields["email"].required = True
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


class PanelAccommodationField(AccommodationChoiceField):
    def label_from_instance(self, obj):
        if obj.is_active:
            return obj.display_name
        return _("%(name)s (hidden)") % {"name": obj.display_name}


class ManualBookingForm(forms.ModelForm):
    """Stay added or edited by the camping (phone, e-mail, walk-in...).

    Price rules such as the minimum stay are only informative here, but a
    confirmed stay cannot take more units than are free unless the camping
    explicitly accepts the overbooking.
    """

    accommodation = PanelAccommodationField(queryset=None, label=_("Accommodation"))
    extras = ExtrasField(queryset=None, required=False, widget=forms.CheckboxSelectMultiple, label=_("Extras"))
    total_override = forms.DecimalField(
        label=_("Agreed price"),
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        help_text=_("Leave it empty to use the price calculated from your price table."),
    )
    ignore_availability = forms.BooleanField(
        label=_("Save it even if there are no free units (overbooking)"), required=False
    )
    language = forms.ChoiceField(
        label=_("Language"), choices=settings.LANGUAGES, help_text=_("Language of the e-mails sent to the guest.")
    )

    class Meta:
        model = BookingRequest
        fields = [
            "accommodation",
            "units",
            "arrival",
            "departure",
            "adults",
            "children",
            "pets",
            "extras",
            "status",
            "name",
            "email",
            "phone",
            "country",
            "language",
            "internal_notes",
        ]
        widgets = {
            "arrival": DATE_WIDGET,
            "departure": DATE_WIDGET,
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"name": _("Guest name")}

    def __init__(self, *args, camping, **kwargs):
        super().__init__(*args, **kwargs)
        self.camping = camping
        self.instance.camping = camping
        self.fields["accommodation"].queryset = camping.accommodations.all()
        self.fields["extras"].queryset = camping.services.filter(is_active=True, mode="optional")
        for name in ("children", "pets"):
            self.fields[name].required = False
        if self.instance.pk:
            # Keep a price agreed by hand unless the camping clears it.
            stored = self.instance.camping_quote.get("total")
            total = self.instance.estimated_total
            if total is not None and stored is not None and Decimal(stored) != total:
                self.initial.setdefault("total_override", total)
        else:
            self.initial.setdefault("status", BookingRequest.Status.CONFIRMED)
            self.initial.setdefault("language", camping.default_language)
        self.quote = None
        self.overbooking = False

    def clean_children(self):
        return self.cleaned_data.get("children") or 0

    def clean_pets(self):
        return self.cleaned_data.get("pets") or 0

    def clean(self):
        cleaned = super().clean()
        accommodation = cleaned.get("accommodation")
        arrival, departure = cleaned.get("arrival"), cleaned.get("departure")
        if not (accommodation and arrival and departure):
            return cleaned
        if departure <= arrival:
            self.add_error("departure", _("The departure date must be after the arrival date."))
            return cleaned
        units = cleaned.get("units") or 1
        if cleaned.get("status") == BookingRequest.Status.CONFIRMED and not cleaned.get("ignore_availability"):
            free = available_units(accommodation, arrival, departure, exclude_pk=self.instance.pk)
            if free < units:
                self.overbooking = True
                self.add_error(
                    None,
                    _(
                        "Only %(free)s unit(s) of “%(name)s” are free for these dates. Tick the overbooking box "
                        "to save it anyway."
                    )
                    % {"free": free, "name": accommodation.display_name},
                )
        self.quote = self._build_quote(cleaned)
        return cleaned

    def _build_quote(self, cleaned):
        return build_quote(
            self.camping,
            cleaned["accommodation"],
            cleaned["arrival"],
            cleaned["departure"],
            adults=cleaned.get("adults") or 0,
            children=cleaned.get("children") or 0,
            pets=cleaned.get("pets") or 0,
            extras=list(cleaned.get("extras") or []),
            units=cleaned.get("units") or 1,
            check_availability=False,
            allow_past=True,
            allow_inactive=True,
        )

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.camping = self.camping
        if not booking.pk:
            booking.source = BookingRequest.Source.MANUAL
        booking.accommodation_name = booking.accommodation_label(self.camping.default_language)
        if self.quote is not None:
            quotes = {}
            for language in dict.fromkeys([self.camping.default_language, booking.language]):
                with translation.override(language):
                    quotes[language] = self._build_quote(self.cleaned_data).as_dict()
            booking.quote = quotes
            override = self.cleaned_data.get("total_override")
            booking.estimated_total = override if override is not None else self.quote.total
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
