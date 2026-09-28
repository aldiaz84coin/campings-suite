"""Helpers for seasons and their periods: overlaps, Easter and yearly copies."""

import re
from datetime import date, timedelta

from core.i18n import translate_value

from .models import Season, SeasonPeriod

EASTER_NAMES = re.compile(r"semana santa|pascua|easter|p[âa]ques|ostern|pasen|pasqua", re.IGNORECASE)
SEASON_KIND_PATTERNS = [
    (
        "special",
        r"semana santa|pascua|easter|paques|ostern|pasen|pasqua|puentes?|navidad|christmas|noel|fiestas?|festival|"
        r"ferragosto|pentecost|pfingsten|pinksteren|reveillon|fin de ano|new year",
    ),
    ("low", r"\bbaja\b|\blow\b|\bbasse\b|nieder|neben|\blaag|\bbassa\b"),
    ("high", r"\balta\b|\bhigh\b|\bhaute\b|\bhoch|haupt|\bhoog"),
    ("mid", r"\bmedia\b|\bmedio\b|\bmid\b|moyenne|mittel|zwischen|midden"),
]


def infer_season_kind(text):
    """``low``, ``mid``, ``high`` or ``special`` from a season name in any language, or None."""
    import unicodedata

    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", str(text or "")) if not unicodedata.combining(ch)
    ).lower()
    for kind, pattern in SEASON_KIND_PATTERNS:
        if re.search(pattern, folded):
            return kind
    return None


def easter_sunday(year):
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    weekday = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * weekday) // 451
    month, day = divmod(h + weekday - 7 * m + 114, 31)
    return date(year, month, day + 1)


def shift_year(day, years=1):
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February
        return date(day.year + years, 2, 28)


def is_easter_period(season, period):
    """A special period around Easter moves with it from one year to the next."""
    if not season.is_special:
        return False
    names = " ".join(str(value) for value in (season.name or {}).values())
    if EASTER_NAMES.search(names):
        return True
    easter = easter_sunday(period.start_date.year)
    return period.start_date <= easter <= period.end_date and (period.end_date - period.start_date).days <= 16


def next_year_dates(season, period):
    if is_easter_period(season, period):
        year = period.start_date.year
        delta = easter_sunday(year + 1) - easter_sunday(year)
        return period.start_date + delta, period.end_date + delta
    return shift_year(period.start_date), shift_year(period.end_date)


def overlapping_season(camping, special, start, end, exclude_season=None):
    """Another season of the same layer (regular or special) using some of these dates.

    Regular seasons cannot overlap each other, and neither can special periods;
    a special period may overlap a regular season (it takes precedence).
    """
    periods = SeasonPeriod.objects.filter(season__camping=camping, start_date__lte=end, end_date__gte=start)
    if special:
        periods = periods.filter(season__kind=Season.Kind.SPECIAL)
    else:
        periods = periods.exclude(season__kind=Season.Kind.SPECIAL)
    if exclude_season is not None and exclude_season.pk:
        periods = periods.exclude(season=exclude_season)
    period = periods.select_related("season").first()
    return period.season if period else None


def copy_periods_to_next_year(camping, today):
    """Repeat the periods of the latest year one year later.

    Prices belong to the season, so only dates are copied. Dates are prepared
    up to next year. Returns ``(year, created, skipped)``.
    """
    seasons = list(camping.seasons.prefetch_related("periods"))
    periods = [(season, period) for season in seasons for period in season.periods.all()]
    if not periods:
        return None, 0, 0
    last_year = max(period.start_date.year for _season, period in periods)
    if last_year > today.year:
        return last_year, 0, 0
    created = skipped = 0
    for season, period in periods:
        if period.start_date.year != last_year:
            continue
        start, end = next_year_dates(season, period)
        same_season = any(other.overlaps(start, end) for other in season.periods.all())
        if same_season or overlapping_season(camping, season.is_special, start, end, exclude_season=season):
            skipped += 1
            continue
        SeasonPeriod.objects.create(season=season, start_date=start, end_date=end)
        created += 1
    return last_year + 1, created, skipped


def has_uncovered_days(camping, seasons, today, days=365):
    """Whether some open day in the coming year falls outside every period."""
    ranges = [(p.start_date, p.end_date) for season in seasons for p in season.periods.all()]
    for offset in range(days):
        day = today + timedelta(days=offset)
        if camping.is_open_on(day) and not any(start <= day <= end for start, end in ranges):
            return True
    return False


def season_label(season):
    return translate_value(season.name, fallback=season.camping.default_language)
