"""Small text helpers for reading camping websites."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

WHITESPACE = re.compile(r"\s+")
FREE_WORDS = re.compile(
    r"\b(gratis|gratuito|gratuita|free|gratuit|gratuite|kostenlos|gratuiti|incluido|incluida|included|inclus|inclusief|"
    r"inklusive|inbegrepen|incluso|compris)\b",
    re.IGNORECASE,
)
# 1.234,56 | 1,234.56 | 12,5 | 12.50 | 12
AMOUNT = re.compile(r"(?<![\d])(\d{1,3}(?:[.\s ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)(?![\d])")
CURRENCY = re.compile(r"€|\beur\b|\beuros?\b", re.IGNORECASE)


def clean(value):
    return WHITESPACE.sub(" ", value or "").strip()


def fold(value):
    """Lowercase without accents, for keyword matching."""
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in value if not unicodedata.combining(ch)).lower()


def _to_decimal(raw):
    raw = raw.replace(" ", "").replace(" ", "")
    if "," in raw and "." in raw:
        decimal_sep = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands = "." if decimal_sep == "," else ","
        raw = raw.replace(thousands, "").replace(decimal_sep, ".")
    elif "," in raw:
        whole, _sep, fraction = raw.rpartition(",")
        raw = f"{whole.replace(',', '')}{fraction}" if len(fraction) == 3 else f"{whole.replace(',', '')}.{fraction}"
    elif raw.count(".") == 1:
        whole, _sep, fraction = raw.partition(".")
        if len(fraction) == 3 and len(whole) <= 3 and whole != "0":
            raw = f"{whole}{fraction}"  # 1.200 = 1200
    else:
        raw = raw.replace(".", "")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value.quantize(Decimal("0.01")) if value < Decimal("100000") else None


def parse_money(text, require_currency=False):
    """First price in ``text`` as a Decimal, 0 for "free"/"included", else None."""
    text = clean(text)
    if not text:
        return None
    if require_currency and not CURRENCY.search(text):
        return None
    match = AMOUNT.search(text)
    if match is None:
        return Decimal("0.00") if FREE_WORDS.search(text) else None
    return _to_decimal(match.group(1))


def looks_like_price(text):
    """A table cell whose content is basically an amount."""
    text = clean(text)
    if not text or len(text) > 40:
        return False
    if FREE_WORDS.fullmatch(text.strip(" .")):
        return True
    stripped = CURRENCY.sub("", text)
    stripped = re.sub(
        r"[/\s]*(noche|night|nuit|nacht|notte|dia|día|day|jour|tag|dag|giorno|pers\w*|pax)\b.*",
        "",
        stripped,
        flags=re.I,
    )
    stripped = stripped.strip(" .:*()+-")
    return bool(stripped) and bool(AMOUNT.fullmatch(stripped))


def first_sentence(text, max_chars=180):
    text = clean(text)
    match = re.match(r"(.{20,}?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    if len(sentence) > max_chars:
        sentence = sentence[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return sentence
