"""Find date ranges written in Spanish, English, French, German, Dutch or Italian.

Examples: "del 1 de julio al 31 de agosto", "01/07 - 31/08/2026",
"July 1 – August 31", "du 1er au 15 juillet", "1. Juli bis 31. August",
"van 1 juli t/m 31 augustus", "dal 1 luglio al 31 agosto".
"""

import re
from datetime import date, timedelta

from .text import fold

MONTH_NAMES = {
    1: "enero ene january jan janvier janv januar janner januari gennaio gen",
    2: "febrero feb february fevrier fevr februar februari febbraio",
    3: "marzo mar march mars marz maerz maart mrt",
    4: "abril abr april apr avril avr aprile",
    5: "mayo may mai mei maggio mag",
    6: "junio jun june juin juni giugno giu",
    7: "julio jul july juillet juil juli luglio lug",
    8: "agosto ago august aug aout augustus",
    9: "septiembre setiembre sept sep set september septembre settembre",
    10: "octubre oct october octobre oktober okt ottobre ott",
    11: "noviembre nov november novembre",
    12: "diciembre dic december dec decembre dezember dez dicembre",
}
MONTHS = {name: number for number, names in MONTH_NAMES.items() for name in names.split()}
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))

_DAY = r"(?P<{d}>[0-3]?\d)(?:o|er|re|st|nd|rd|th|\.)?"
_YEAR = r"(?:,?\s*(?:de\s+|del\s+)?(?P<{y}>(?:19|20)\d{{2}}))?"

TEXT_DAY_MONTH = r"{day}\s*(?:de\s+|of\s+)?(?P<{m}>{months})\.?(?![a-z]){year}"
TEXT_MONTH_DAY = r"(?P<{m}>{months})\.?\s+{day}(?![\d]){year}"
NUMERIC = r"(?P<{d}>[0-3]?\d)(?:[/-](?P<{m}>[01]?\d)(?:[/-](?P<{y}>(?:19|20)?\d{{2}}))?|\.(?P<{m}2>[01]?\d)\.(?P<{y}2>(?:19|20)\d{{2}})?)(?![\d/])"

CONNECTOR = r"\s*(?:-|–|—|al|a|hasta|to|till|until|through|thru|au|a|jusqu'?au|bis|bis zum|zum|tot|t/m|tot en met|fino al|fino a|y el)\s*"


def _token(prefix):
    day = _DAY.format(d=f"{prefix}d")
    year = _YEAR.format(y=f"{prefix}y")
    return "(?:{})".format(
        "|".join(
            [
                TEXT_DAY_MONTH.format(day=day, m=f"{prefix}m", months=_MONTH, year=year),
                TEXT_MONTH_DAY.format(
                    m=f"{prefix}m_", months=_MONTH, day=_DAY.format(d=f"{prefix}d_"), year=_YEAR.format(y=f"{prefix}y_")
                ),
                NUMERIC.format(d=f"{prefix}dn", m=f"{prefix}mn", y=f"{prefix}yn"),
            ]
        )
    )


RANGE = re.compile(r"(?<![\w/.])" + _token("a") + CONNECTOR + _token("b"), re.IGNORECASE)
# "del 1 al 15 de julio", "1-15 July", "du 1er au 15 juillet"
SAME_MONTH = re.compile(
    r"(?<![\w/.])"
    + _DAY.format(d="d1")
    + CONNECTOR
    + _DAY.format(d="d2")
    + r"\s*(?:de\s+)?(?P<m>"
    + _MONTH
    + r")\.?(?![a-z])"
    + _YEAR.format(y="y"),
    re.IGNORECASE,
)
# "July 1-15"
SAME_MONTH_MD = re.compile(
    r"(?P<m>"
    + _MONTH
    + r")\.?\s+"
    + _DAY.format(d="d1")
    + CONNECTOR
    + _DAY.format(d="d2")
    + r"(?![\d])"
    + _YEAR.format(y="y"),
    re.IGNORECASE,
)
YEAR_MENTION = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def _part(groups, prefix):
    for day_key, month_key, year_key in (
        (f"{prefix}d", f"{prefix}m", f"{prefix}y"),
        (f"{prefix}d_", f"{prefix}m_", f"{prefix}y_"),
        (f"{prefix}dn", f"{prefix}mn", f"{prefix}yn"),
        (f"{prefix}dn", f"{prefix}mn2", f"{prefix}yn2"),
    ):
        day, month = groups.get(day_key), groups.get(month_key)
        if day and month:
            month_number = int(month) if month.isdigit() else MONTHS.get(fold(month).rstrip("."))
            year = groups.get(year_key)
            if year and len(year) == 2:
                year = f"20{year}"
            return int(day), month_number, int(year) if year else None
    return None


def _make(day, month, year):
    try:
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _build(start, end, default_year, today):
    (d1, m1, y1), (d2, m2, y2) = start, end
    if not m1 or not m2:
        return None
    explicit = y1 or y2
    year1 = y1 or y2 or default_year or today.year
    year2 = y2 or year1
    first, last = _make(d1, m1, year1), _make(d2, m2, year2)
    if first is None or last is None:
        return None
    if last < first and not y2:
        last = _make(d2, m2, year2 + 1)
    if last is None or last < first or (last - first).days > 366:
        return None
    if not explicit and not default_year and last < today:
        # Without a year, take the next time these dates come round.
        first, last = _make(d1, m1, year1 + 1), _make(d2, m2, (last.year) + 1)
        if first is None or last is None:
            return None
    return first, last


def find_periods(text, today, default_year=None):
    """All the date ranges found in ``text`` as ``(start, end)`` tuples (both included)."""
    folded = fold(text)
    periods = []
    taken = []

    def add(span, period):
        if period and not any(span[0] < end and start < span[1] for start, end in taken):
            taken.append(span)
            if period not in periods:
                periods.append(period)

    for match in SAME_MONTH.finditer(folded):
        groups = match.groupdict()
        month = MONTHS.get(groups["m"].rstrip("."))
        year = int(groups["y"]) if groups.get("y") else None
        add(
            match.span(),
            _build((int(groups["d1"]), month, year), (int(groups["d2"]), month, year), default_year, today),
        )
    for match in SAME_MONTH_MD.finditer(folded):
        groups = match.groupdict()
        month = MONTHS.get(groups["m"].rstrip("."))
        year = int(groups["y"]) if groups.get("y") else None
        add(
            match.span(),
            _build((int(groups["d1"]), month, year), (int(groups["d2"]), month, year), default_year, today),
        )
    for match in RANGE.finditer(folded):
        groups = match.groupdict()
        start, end = _part(groups, "a"), _part(groups, "b")
        if start and end:
            add(match.span(), _build(start, end, default_year, today))
    return sorted(periods)


def main_year(text, today):
    """The season year a price list talks about ("Tarifas 2027"), if any."""
    counts = {}
    for match in YEAR_MENTION.finditer(text or ""):
        year = int(match.group(1))
        if today.year - 1 <= year <= today.year + 2:
            counts[year] = counts.get(year, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda year: (counts[year], year))


def whole_year(start, end):
    return start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31


def days(period):
    start, end = period
    return (end - start + timedelta(days=1)).days
