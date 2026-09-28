"""Price lists: tables (or lines) with items and their price in each season."""

import re
import statistics
from decimal import Decimal
from urllib.parse import urlsplit

from campings.seasons import infer_season_kind

from . import dates
from .text import clean, fold, looks_like_price, parse_money

ACCOMMODATION_WORDS = [
    ("caravan_rental", r"alquiler de caravanas?|caravanas? de alquiler|rental caravans?|caravane a louer"),
    ("tent_rental", r"tiendas? de alquiler|alquiler de tiendas?|rental tents?|tentes? de location|mietzelt"),
    ("mobile_home", r"mobil[- ]?homes?|mobile[- ]?homes?|casas? moviles?|mobil-?heim|stacaravan|mobilhome"),
    ("bungalow", r"bungalows?"),
    ("glamping", r"glamping|safari|\btipis?\b|\blodges?\b|bell tents?|tente lodge"),
    ("cabin", r"cabanas?|\bcabins?\b|\bchalets?\b|cabanes?|blockhaus|houten huisje|casette in legno"),
    ("apartment", r"apartamentos?|apartments?|appartements?|ferienwohnung|appartament"),
    ("room", r"\bhabitacion(?:es)?\b|\brooms?\b|\bchambres?\b|\bzimmer\b|\bkamers?\b|\bcamere\b"),
    ("pitch", r"parcelas?|\bpitch(?:es)?\b|emplacements?|stellplatz|kampeerplaats|staanplaats|piazzol[ae]|acampada"),
]
ACCOMMODATION_PATTERNS = [(kind, re.compile(pattern, re.IGNORECASE)) for kind, pattern in ACCOMMODATION_WORDS]

# pattern, unit, mode, icon (the first match wins)
SERVICE_RULES = [
    (
        r"tasa turistica|impuesto turistico|ecotasa|tourist tax|taxe de sejour|kurtaxe|toeristenbelasting|"
        r"tassa di soggiorno",
        "adult_night",
        "mandatory",
        "receipt",
    ),
    (r"adult|erwachsene|volwassene|persona mayor|mayores de", "adult_night", "mandatory", "user"),
    (
        r"\bnin[oa]s?\b|child|\bkids?\b|enfant|\bkind(?:er)?\b|bambin|menores|infantil",
        "child_night",
        "mandatory",
        "baby",
    ),
    (
        r"perros?|mascotas?|\bdogs?\b|\bpets?\b|chiens?|animal|\bhunde?\b|\bhond(?:en)?\b|huisdier|\bcane\b",
        "pet_night",
        "mandatory",
        "dog",
    ),
    (
        r"\bpersonas?\b|\bpersons?\b|\bpeople\b|personnes?|\bpersonen\b|\bpersone\b",
        "person_night",
        "mandatory",
        "users",
    ),
    (
        r"electricidad|electricity|electricite|\bstrom\b|elektriciteit|elettricita|\bcorriente\b|\bluz\b|\bkwh\b",
        "night",
        "optional",
        "plug-zap",
    ),
    (r"autocaravanas?|motorhomes?|\bcampers?\b|camping-?cars?|wohnmobil|camper ?vans?", "night", "optional", "van"),
    (r"caravanas?|caravans?|wohnwagen|caravane", "night", "optional", "caravan"),
    (r"\bcoches?\b|automovil|\bcars?\b|voitures?|\bauto\b|\bpkw\b|vehiculos?", "night", "optional", "car"),
    (r"\bmotos?\b|motorbikes?|motorcycles?|motorrad", "night", "optional", "motorbike"),
    (r"\btiendas?\b|\btents?\b|\btentes?\b|\bzelte?\b|\btenda\b", "night", "optional", "tent"),
    (r"visitas?|visitors?|visiteurs?|besucher|bezoekers?|visitator", "person_stay", "optional", "users"),
    (r"ropa de cama|sabanas|bed linen|linge de lit|bettwasche|beddengoed|biancheria", "stay", "optional", "bed"),
    (r"toallas?|towels?|serviettes|handtucher|handdoeken|asciugamani", "stay", "optional", "shirt"),
    (r"limpieza|cleaning|menage|nettoyage|endreinigung|schoonmaak|pulizia", "stay", "optional", "spray-can"),
    (r"desayuno|breakfast|petit[- ]dejeuner|fruhstuck|ontbijt|colazione", "person_night", "optional", "coffee"),
    (r"nevera|frigorifico|fridge|frigo|kuhlschrank|koelkast", "night", "optional", "refrigerator"),
    (r"bicicletas?|\bbikes?\b|\bvelos?\b|fahrrad|fiets|\bbici\b", "night", "optional", "bike"),
    (r"barbacoa|barbecue|\bbbq\b", "stay", "optional", "flame"),
    (r"late check-?out|salida tardia|depart tardif", "stay", "optional", "clock"),
]
SERVICE_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), unit, mode, icon) for pattern, unit, mode, icon in SERVICE_RULES
]
SEASON_WORDS = re.compile(
    r"temporada|season|saison|seizoen|stagione|\bt\.\s*(?:baja|media|alta)|\bbaja\b|\bmedia\b|\balta\b|\blow\b|\bmid\b|"
    r"\bhigh\b|basse|moyenne|haute|laag|midden|hoog|bassa|semana santa|pascua|easter|paques|ostern|pasen|pasqua|"
    r"puentes?|navidad|christmas",
    re.IGNORECASE,
)
PRICE_PAGE_WORDS = re.compile(r"tarifa|precio|price|rates|tarif|preise|prijzen|prezzi|listino", re.IGNORECASE)
GUESTS = re.compile(
    r"(\d{1,2})\s*(?:pax|pers(?:onas|ons|onnes|onen|one)?\.?|people|plazas|places|plaatsen|posti)\b", re.I
)
GUESTS_UP_TO = re.compile(r"(?:hasta|up to|jusqu'a|bis zu|tot|fino a)\s*(\d{1,2})", re.IGNORECASE)
LINE_PRICE = re.compile(
    r"^(?P<label>[^\d€\n]{3,60}?)[\s.:·…_–-]+(?:desde |from |a partir de )?(?P<price>€\s*\d{1,4}(?:[.,]\d{1,2})?|"
    r"\d{1,4}(?:[.,]\d{1,2})?\s*(?:€|eur\b|euros?\b))",
    re.IGNORECASE,
)
NUMERIC_DATE = re.compile(r"\d{1,2}\s*[/.-]\s*\d{1,2}(?:\s*[/.-]\s*\d{2,4})?")


def classify(label):
    """Guess whether a price list row is an accommodation or a service."""
    folded = fold(label)
    rental = re.search(r"alquiler|rental|location|verhuur|miete|noleggio", folded)
    for kind, pattern in ACCOMMODATION_PATTERNS:
        if pattern.search(folded) and (kind not in ("tent_rental", "caravan_rental") or rental):
            guests = [int(value) for value in GUESTS.findall(folded) + GUESTS_UP_TO.findall(folded)]
            max_guests = max([value for value in guests if 1 <= value <= 20], default=None)
            return {
                "kind": "accommodation",
                "accommodation_kind": kind,
                "max_guests": max_guests or (6 if kind == "pitch" else 4),
                "unit": "night",
                "mode": "",
                "icon": "",
            }
    for pattern, unit, mode, icon in SERVICE_PATTERNS:
        if pattern.search(folded):
            return {"kind": "service", "unit": unit, "mode": mode, "icon": icon}
    return {"kind": "service", "unit": "night", "mode": "optional", "icon": "tag"}


def season_like(text, today):
    return bool(SEASON_WORDS.search(fold(text))) or bool(dates.find_periods(text, today))


def strip_dates(text):
    """Season name without the dates written in it: "T. Alta (01/07-31/08)" -> "T. Alta"."""
    folded = fold(text)
    if len(folded) == len(text):
        spans = [
            m.span()
            for pattern in (dates.RANGE, dates.SAME_MONTH, dates.SAME_MONTH_MD)
            for m in pattern.finditer(folded)
        ]
        for start, end in sorted(spans, reverse=True):
            text = text[:start] + " " + text[end:]
    text = NUMERIC_DATE.sub(" ", text)
    text = re.sub(
        r"\b(?:del|de|desde|from|du|vom|von|van|dal|al|to|au|bis|tot|y|and|et|und|en|e)\s*$",
        "",
        clean(text),
        flags=re.I,
    )
    text = re.sub(r"\(\s*[-–/,]*\s*\)", " ", text)
    return clean(text).strip(" :-–,()/")


def _grid(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = []
        for cell in tr.find_all(["td", "th"], recursive=False):
            text = clean(cell.get_text(" "))
            span = str(cell.get("colspan") or "1")
            cells.extend([text] * min(int(span) if span.isdigit() else 1, 12))
        if any(cells):
            rows.append(cells)
    return rows


def _is_price_row(row):
    return any(looks_like_price(cell) for cell in row[1:])


def _transpose(grid):
    width = max(len(row) for row in grid)
    padded = [row + [""] * (width - len(row)) for row in grid]
    return [list(column) for column in zip(*padded, strict=True)]


def _caption(table):
    caption = table.find("caption")
    if caption:
        return clean(caption.get_text(" "))
    heading = table.find_previous(["h1", "h2", "h3", "h4", "h5"])
    return clean(heading.get_text(" ")) if heading else ""


def read_table(table, today):
    """``{"columns": [header, ...], "rows": [{label, prices, section}], "caption": str}`` or None."""
    grid = _grid(table)
    if len(grid) < 2:
        return None
    header_index = None
    for index, row in enumerate(grid[:4]):
        if _is_price_row(row):
            break
        if len(set(filter(None, row))) <= 1:
            continue  # empty or a section row spanning the whole table ("BUNGALOWS")
        if len(row) >= 2 and any(clean(cell) for cell in row[1:]):
            header_index = index
    header = grid[header_index] if header_index is not None else []
    body = grid[header_index + 1 :] if header_index is not None else grid

    # Seasons as rows and items as columns: turn it round.
    row_labels = [row[0] for row in body if row and row[0]]
    if header and row_labels and sum(season_like(label, today) for label in row_labels) > len(row_labels) / 2:
        column_items = [cell for cell in header[1:] if cell]
        if column_items and sum(season_like(cell, today) for cell in column_items) < len(column_items) / 2:
            flipped = _transpose([header, *body])
            header, body = flipped[0], flipped[1:]

    rows, section = [], ""
    for row in body:
        if not row or looks_like_price(row[0]):
            continue
        label, cells = row[0], row[1:]
        prices = [parse_money(cell) if looks_like_price(cell) else None for cell in cells]
        if not any(price is not None for price in prices):
            if len(set(filter(None, row))) == 1:
                section = label  # e.g. a "BUNGALOWS" separator row
            continue
        rows.append({"label": label, "prices": prices, "section": section})
    if not rows:
        return None
    width = max(len(row["prices"]) for row in rows)
    columns = [(header[index + 1] if index + 1 < len(header) else "") for index in range(width)]
    return {"columns": columns, "rows": rows, "caption": _caption(table)}


def read_lines(text):
    """Single prices written as lines: "Adulto ......... 6,50 €"."""
    rows = []
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    for index, line in enumerate(lines):
        match = LINE_PRICE.match(line)
        if match:
            label = clean(match.group("label")).strip(" .:-–")
            price = parse_money(match.group("price"))
        elif index + 1 < len(lines) and looks_like_price(lines[index + 1]) and 3 <= len(line) <= 60:
            label, price = line.strip(" .:-–"), parse_money(lines[index + 1])
            if not re.search(r"[a-zA-Z]", label) or looks_like_price(label):
                continue
        else:
            continue
        if price is not None and label and not NUMERIC_DATE.search(label):
            rows.append({"label": label, "prices": [price], "section": ""})
    return rows


class PriceCollector:
    """Accumulates seasons and priced items from every page of the website."""

    def __init__(self, today):
        self.today = today
        self.seasons = []
        self.items = []
        self.pdfs = []
        self.texts = []

    def _season(self, header, default_year):
        periods = dates.find_periods(header, self.today, default_year)
        name = strip_dates(header)
        identity = fold(name) or "|".join(start.isoformat() for start, _end in periods) or header
        kind = infer_season_kind(name) if name else None
        for season in self.seasons:
            same_kind = kind in ("low", "mid", "high") and season["kind"] == kind
            if season["identity"] == identity or same_kind:
                for period in periods:
                    if period not in season["periods"]:
                        season["periods"].append(period)
                if len(name) > len(season["name"]) and not name.startswith("#"):
                    season["name"] = name[:60]  # "Temporada baja" rather than "T. Baja"
                return season
        season = {
            "key": f"s{len(self.seasons) + 1}",
            "name": name[:60],
            "kind": kind,
            "periods": list(periods),
            "identity": identity,
        }
        self.seasons.append(season)
        return season

    def add_page(self, page):
        text = page.text
        default_year = dates.main_year(text, self.today) if PRICE_PAGE_WORDS.search(text[:4000]) else None
        self.texts.append((text, default_year))
        for table in page.soup.find_all("table"):
            data = read_table(table, self.today)
            if data is None:
                continue
            price_columns = [
                index
                for index in range(len(data["columns"]))
                if any(index < len(row["prices"]) and row["prices"][index] is not None for row in data["rows"])
            ]
            single_header = data["columns"][price_columns[0]] if len(price_columns) == 1 else ""
            seasonal = len(price_columns) > 1 or (
                len(price_columns) == 1 and season_like(single_header or data["caption"], self.today)
            )
            column_seasons = {}
            if seasonal:
                for index in price_columns:
                    header = data["columns"][index] or (data["caption"] if len(price_columns) == 1 else "")
                    column_seasons[index] = self._season(header or f"#{index + 1}", default_year)
            for row in data["rows"]:
                self._add_item(row, column_seasons, price_columns, page.url)
        if page.role == "prices":
            # Prices written as lines ("Tasa turística ... 0,50 €"); rows already
            # read from a table are recognised and skipped.
            known = {fold(item["label"]) for item in self.items}
            for row in read_lines(text):
                if fold(row["label"]) not in known:
                    self._add_item(row, {}, [0], page.url)
        for link in page.soup.find_all("a", href=True):
            href = link["href"]
            if urlsplit(href).path.lower().endswith(".pdf") and PRICE_PAGE_WORDS.search(
                fold(href + " " + link.get_text())
            ):
                url = page.absolute(href)
                if url not in self.pdfs:
                    self.pdfs.append(url)

    def _add_item(self, row, column_seasons, price_columns, source):
        label = clean(row["label"])[:120]
        if len(label) < 2:
            return
        prices = {
            index: row["prices"][index]
            for index in price_columns
            if index < len(row["prices"]) and row["prices"][index] is not None
        }
        if not prices:
            return
        seasonal = {
            column_seasons[index]["key"]: str(price) for index, price in prices.items() if index in column_seasons
        }
        folded = fold(f"{row.get('section', '')} {label}")
        for item in self.items:
            if item["identity"] == folded:  # same row in another table (e.g. one table per season)
                for key, value in seasonal.items():
                    item["prices"].setdefault(key, value)
                values = [Decimal(value) for value in item["prices"].values()] or [Decimal(item["base"])]
                item["base"] = str(min(values))
                return
        guess = classify(f"{row.get('section', '')} {label}")
        base = min(prices.values()) if seasonal else next(iter(prices.values()))
        self.items.append(
            {
                "key": f"i{len(self.items) + 1}",
                "identity": folded,
                "label": label,
                "section": row.get("section", ""),
                "source": source,
                "prices": seasonal,
                "base": str(base),
                **guess,
            }
        )

    def _periods_from_text(self):
        """Dates written next to a season name: "Temporada alta: 01/07 - 31/08"."""
        for text, default_year in self.texts:
            for line in text.splitlines():
                if len(line) > 400:
                    continue
                periods = dates.find_periods(line, self.today, default_year)
                if not periods:
                    continue
                folded = fold(line)
                line_kind = infer_season_kind(folded)
                for season in self.seasons:
                    name = fold(season["name"])
                    by_name = bool(name) and name in folded
                    by_kind = not season["periods"] and season["kind"] and season["kind"] == line_kind
                    if by_name or by_kind:
                        for period in periods:
                            if period not in season["periods"]:
                                season["periods"].append(period)
                        break

    def _rank_unnamed(self, seasons):
        """Seasons whose name says nothing get low/mid/high from their prices."""
        if all(season["kind"] for season in seasons):
            return
        levels = {}
        for season in seasons:
            values = [Decimal(item["prices"][season["key"]]) for item in self.items if season["key"] in item["prices"]]
            levels[season["key"]] = statistics.median(values) if values else Decimal("0")
        ordered = sorted(seasons, key=lambda season: levels[season["key"]])
        kinds = ["low", "mid", "high"]
        for position, season in enumerate(ordered):
            if not season["kind"]:
                season["kind"] = "mid" if len(ordered) == 1 else kinds[min(round(position * 2 / (len(ordered) - 1)), 2)]
            if not season["name"] or season["name"].startswith("#"):
                season["name"] = ""

    def result(self):
        self._periods_from_text()
        seasons = [season for season in self.seasons if any(season["key"] in item["prices"] for item in self.items)]
        self._rank_unnamed(seasons)
        return {
            "seasons": [
                {
                    "key": season["key"],
                    "name": season["name"],
                    "kind": season["kind"],
                    "periods": [[start.isoformat(), end.isoformat()] for start, end in sorted(season["periods"])],
                }
                for season in seasons
            ],
            "items": [{key: value for key, value in item.items() if key != "identity"} for item in self.items[:80]],
            "pdfs": self.pdfs[:5],
        }
