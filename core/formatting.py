from decimal import Decimal, InvalidOperation

from django.utils.formats import number_format
from django.utils.translation import get_language

CURRENCY_SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$", "CHF": "CHF"}
_SYMBOL_FIRST_LANGUAGES = ("en",)


def format_money(value, currency="EUR"):
    """``45`` -> ``45 €`` (``€45`` in English); decimals only when needed."""
    if value in (None, ""):
        return ""
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    decimals = 0 if amount == amount.to_integral_value() else 2
    number = number_format(amount, decimal_pos=decimals, use_l10n=True, force_grouping=True)
    symbol = CURRENCY_SYMBOLS.get(currency or "EUR", currency or "")
    if (get_language() or "").split("-")[0] in _SYMBOL_FIRST_LANGUAGES and len(symbol) == 1:
        return f"{symbol}{number}"
    return f"{number} {symbol}"
