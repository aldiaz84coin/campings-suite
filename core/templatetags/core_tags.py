import json

from django import template
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.templatetags.static import static
from django.urls import translate_url
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.translation import get_language

from core.formatting import format_money
from core.i18n import language_name, translate_value
from core.urlutils import camping_reverse

register = template.Library()


@register.filter
def tr(value, fallback=None):
    """``{{ camping.description|tr }}`` -> text in the active language."""
    return translate_value(value, fallback=fallback)


@register.filter
def money(value, currency="EUR"):
    return format_money(value, currency)


@register.simple_tag
def icon(name, css_class="", label=""):
    href = f"{static('icons/sprite.svg')}#{name}"
    if label:
        return format_html(
            '<svg class="icon {}" role="img" aria-label="{}" focusable="false"><use href="{}"></use></svg>',
            css_class,
            label,
            href,
        )
    return format_html(
        '<svg class="icon {}" aria-hidden="true" focusable="false"><use href="{}"></use></svg>', css_class, href
    )


@register.simple_tag(takes_context=True)
def language_links(context):
    """Links to the current page in every platform language."""
    request = context.get("request")
    path = request.get_full_path() if request else "/"
    current = get_language()
    return [
        {"code": code, "name": language_name(code), "url": translate_url(path, code), "current": code == current}
        for code, _name in settings.LANGUAGES
    ]


@register.simple_tag(takes_context=True)
def camping_url(context, name, camping, **kwargs):
    return camping_reverse(context.get("request"), name, camping, **kwargs)


@register.simple_tag(takes_context=True)
def query_string(context, **changes):
    """Current query string with some parameters replaced (for pagination)."""
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for key, value in changes.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode() if hasattr(params, "urlencode") else urlencode(params)
    return f"?{encoded}" if encoded else "?"


def _relative_luminance(hex_color):
    hex_color = (hex_color or "").lstrip("#")
    if len(hex_color) != 6:
        return 0.0
    channels = []
    for i in (0, 2, 4):
        c = int(hex_color[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@register.filter
def contrast_text(hex_color):
    """Readable text colour (white or near black) on top of ``hex_color``."""
    luminance = _relative_luminance(hex_color)
    # Contrast ratio against white vs. against #1c1917.
    white = 1.05 / (luminance + 0.05)
    dark = (luminance + 0.05) / (0.0117 + 0.05)
    return "#ffffff" if white >= dark else "#1c1917"


@register.filter
def get_item(mapping, key):
    if not mapping:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag
def json_ld(data):
    payload = json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')  # noqa: S308 - escaped above


@register.filter
def lang_name(code):
    return language_name(code)


@register.filter
def times(value):
    """``{% for _ in camping.stars|times %}`` -> repeat n times."""
    try:
        return range(int(value or 0))
    except (TypeError, ValueError):
        return range(0)


@register.filter
def digits(value):
    """Keep only digits (for wa.me / tel: links)."""
    return "".join(ch for ch in str(value or "") if ch.isdigit())
