"""Helpers for content stored in several languages as ``{"es": ..., "en": ...}``."""

from django.conf import settings
from django.utils.translation import get_language, get_language_info


def platform_language_codes():
    return [code for code, _name in settings.LANGUAGES]


def language_name(code):
    """Native name of a language ("Español", "Deutsch"...)."""
    try:
        name = get_language_info(code)["name_local"]
    except KeyError:
        name = dict(settings.LANGUAGES).get(code, code)
    return name[:1].upper() + name[1:]


def translate_value(value, lang=None, fallback=None):
    """Pick the best translation from a ``{lang: text}`` mapping.

    Order: requested language, ``fallback`` (usually the camping's default
    language), the platform default language and finally any non-empty value.
    """
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return str(value)
    lang = lang or get_language() or settings.LANGUAGE_CODE
    for code in (lang, lang.split("-")[0], fallback, settings.LANGUAGE_CODE):
        if code and value.get(code):
            return value[code]
    for text in value.values():
        if text:
            return text
    return ""


def has_translation(value, lang):
    return bool(isinstance(value, dict) and value.get(lang))
