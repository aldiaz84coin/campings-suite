"""A model field that keeps one text per language in a JSON column."""

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .i18n import language_name, platform_language_codes


class TranslatedWidget(forms.MultiWidget):
    template_name = "core/widgets/translated.html"

    class Media:
        # Only rendered where {{ form.media }} is used (the Django admin).
        css = {"all": ("core/i18n-admin.css",)}

    def __init__(self, languages=None, textarea=False, attrs=None, required_language=None):
        self.languages = list(languages or platform_language_codes())
        self.textarea = textarea
        self.required_language = required_language
        widgets = {}
        for code in self.languages:
            if textarea:
                widgets[code] = forms.Textarea(attrs={"lang": code, "rows": 5})
            else:
                widgets[code] = forms.TextInput(attrs={"lang": code})
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if isinstance(value, dict):
            return [value.get(code, "") for code in self.languages]
        if isinstance(value, str) and value:
            # Plain text (e.g. legacy data) is shown in the first language.
            return [value] + [""] * (len(self.languages) - 1)
        return [""] * len(self.languages)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        for subwidget, code in zip(context["widget"]["subwidgets"], self.languages, strict=False):
            subwidget["lang_code"] = code
            subwidget["lang_name"] = language_name(code)
            subwidget["is_required_language"] = code == self.required_language
        context["widget"]["textarea"] = self.textarea
        return context

    def id_for_label(self, id_):
        if id_ and self.languages:
            return f"{id_}_{self.languages[0]}"
        return ""


class TranslatedFormField(forms.MultiValueField):
    """Form field rendering one input per language.

    ``required=True`` means the *required language* (the camping's default
    language, or the first one) must be filled in; the rest are optional.
    """

    def __init__(
        self,
        *,
        languages=None,
        textarea=False,
        max_chars=None,
        required_language=None,
        encoder=None,
        decoder=None,
        **kwargs,
    ):
        self.textarea = textarea
        self.max_chars = max_chars
        self.languages = list(languages or platform_language_codes())
        self.required_language = required_language or self.languages[0]
        kwargs.pop("widget", None)
        kwargs.pop("max_length", None)
        fields = self._make_subfields()
        widget = TranslatedWidget(self.languages, textarea=textarea, required_language=self.required_language)
        super().__init__(fields=fields, widget=widget, require_all_fields=False, **kwargs)

    def _make_subfields(self):
        return tuple(forms.CharField(required=False, max_length=self.max_chars) for _code in self.languages)

    def set_languages(self, languages, required_language=None):
        self.languages = list(languages)
        self.required_language = required_language if required_language in self.languages else self.languages[0]
        self.fields = self._make_subfields()
        for subfield in self.fields:
            subfield.error_messages.setdefault("incomplete", self.error_messages["incomplete"])
        attrs = self.widget.attrs
        self.widget = TranslatedWidget(
            self.languages, textarea=self.textarea, attrs=attrs, required_language=self.required_language
        )

    def compress(self, data_list):
        result = {}
        for code, text in zip(self.languages, data_list or [], strict=False):
            text = (text or "").strip()
            if text:
                result[code] = text
        return result

    def validate(self, value):
        if self.required and not (value or {}).get(self.required_language):
            raise ValidationError(
                _("This field is required in %(language)s.") % {"language": language_name(self.required_language)},
                code="required",
            )

    def has_changed(self, initial, data):
        initial = initial or {}
        if not isinstance(initial, dict):
            initial = {}
        data = data or []
        for code, text in zip(self.languages, data, strict=False):
            if (initial.get(code) or "") != (text or "").strip():
                return True
        return False


class TranslatedField(models.JSONField):
    """JSON column holding ``{"es": "...", "en": "..."}``."""

    description = _("Text in several languages")

    def __init__(self, *args, textarea=False, max_chars=None, **kwargs):
        self.textarea = textarea
        self.max_chars = max_chars
        kwargs.setdefault("default", dict)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.textarea:
            kwargs["textarea"] = True
        if self.max_chars:
            kwargs["max_chars"] = self.max_chars
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        # Skip JSONField.formfield(): it would force forms.JSONField.
        return models.Field.formfield(
            self,
            **{
                "form_class": TranslatedFormField,
                "textarea": self.textarea,
                "max_chars": self.max_chars,
                "show_hidden_initial": False,
                **kwargs,
            },
        )


class TranslatedFormMixin:
    """Adapts translated fields of a form to a set of content languages.

    Values stored for languages that are not currently editable (for example a
    language the camping disabled) are preserved when saving.
    """

    def setup_translated_fields(self, languages, required_language=None):
        for field in self.fields.values():
            if isinstance(field, TranslatedFormField):
                field.set_languages(languages, required_language)

    def _post_clean(self):
        for name, field in self.fields.items():
            if isinstance(field, TranslatedFormField) and name in getattr(self, "cleaned_data", {}):
                initial = self.get_initial_for_field(field, name) or {}
                if not isinstance(initial, dict):
                    initial = {}
                hidden = {code: text for code, text in initial.items() if code not in field.languages and text}
                if hidden:
                    self.cleaned_data[name] = {**(self.cleaned_data[name] or {}), **hidden}
        super()._post_clean()
