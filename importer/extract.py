"""Read what a camping's website says about it.

Everything here is best effort: websites are very different, so each piece
of information is looked for in several places (schema.org data, meta tags,
links, visible text) and the camping reviews the result before importing.
"""

import copy
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

from . import dates
from .text import clean, first_sentence, fold

logger = logging.getLogger(__name__)

CAMPING_TYPES = {"campground", "rvpark", "lodgingbusiness", "resort", "hotel", "hostel", "vacationrental"}
BUSINESS_TYPES = CAMPING_TYPES | {
    "localbusiness",
    "organization",
    "touristattraction",
    "place",
    "sportsactivitylocation",
}
NOISE = re.compile(
    r"cookie|consent|gdpr|rgpd|newsletter|popup|modal|breadcrumb|copyright|menu|navbar|nav-|sidebar|widget|share|social",
    re.IGNORECASE,
)
LEGAL_TEXT = re.compile(
    r"cookie|privacidad|privacy|aviso legal|legal notice|mentions legales|datenschutz|impressum|todos los derechos|"
    r"all rights reserved|©|&copy;|javascript|navegador|browser",
    re.IGNORECASE,
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".avif")
SKIP_IMAGE = re.compile(
    r"logo|icon|sprite|favicon|flag|bandera|avatar|placeholder|loader|loading|spinner|blank|pixel|spacer|captcha|"
    r"badge|sello|award|tripadvisor|booking|payment|visa|mastercard|paypal|facebook|instagram|whatsapp|twitter|"
    r"youtube|google|qr[-_]|emoji|cookie|gravatar|arrow|flecha|button|boton|mapa|plano|map[-_.]",
    re.IGNORECASE,
)
GALLERY_HINT = re.compile(r"galer|gallery|slider|carousel|swiper|slick|hero|banner|portada|lightbox|fancybox", re.I)
WP_SIZE = re.compile(r"-(\d{2,4})x(\d{2,4})(?=\.(?:jpe?g|png|webp)$)", re.IGNORECASE)
COUNTRIES = {
    "es": "España",
    "fr": "France",
    "pt": "Portugal",
    "it": "Italia",
    "de": "Deutschland",
    "nl": "Nederland",
    "be": "Belgique",
    "ad": "Andorra",
    "gb": "United Kingdom",
    "uk": "United Kingdom",
    "ch": "Schweiz",
    "at": "Österreich",
}
PHONE_PREFIX_COUNTRY = {
    "34": "España",
    "33": "France",
    "351": "Portugal",
    "39": "Italia",
    "49": "Deutschland",
    "31": "Nederland",
    "32": "Belgique",
    "376": "Andorra",
    "44": "United Kingdom",
}

FACILITY_KEYWORDS = {
    "reception_24h": r"recepcion (?:abierta )?24|24 ?h(?:oras)? de recepcion|24[- ]?hours? reception|reception (?:open )?24|"
    r"accueil 24|rezeption 24|receptie 24",
    "wifi": r"\bwi-?fi\b|\bwlan\b",
    "restaurant": r"\brestaurantes?\b|\bristorante\b",
    "bar": r"\bbar\b|\bcafeteria\b|snack[- ]?bar|\bbuvette\b",
    "supermarket": r"supermercado|supermarket|supermarche|supermarkt|mini-?market|epicerie|superette|alimentacion",
    "bakery": r"panaderia|pan fresco|fresh bread|boulangerie|pain frais|backerei|brotchen|bakkerij|vers brood|"
    r"panetteria|pane fresco",
    "takeaway": r"comida para llevar|take[- ]?away|plats a emporter|imbiss|afhaalmaaltijden|da asporto|pizzeria",
    "laundry": r"lavanderia|laundry|laverie|lave-linge|waschmaschine|wasmachine|wasserette|lavatrice|lavadoras",
    "fridge_rental": r"alquiler de neveras?|fridge (?:rental|hire)|location de (?:frigo|refrigerateur)|kuhlschrank|koelkast",
    "safe": r"caja fuerte|cajas de seguridad|safe deposit|coffre-fort|\btresor\b|\bkluis\b|cassett[ae] di sicurezza",
    "atm": r"cajero automatico|\batm\b|cash machine|distributeur de billets|geldautomat|pinautomaat|bancomat",
    "first_aid": r"primeros auxilios|botiquin|first aid|premiers secours|erste hilfe|\behbo\b|pronto soccorso",
    "pool": r"piscina|swimming[- ]?pool|\bpools?\b|piscine|schwimmbad|freibad|zwembad",
    "kids_pool": r"piscina infantil|chapoteo|paddling pool|kids'? pool|children'?s pool|pataugeoire|kinderbecken|"
    r"planschbecken|pierenbad|piscina per bambini",
    "heated_pool": r"piscina (?:cubierta|climatizada)|heated (?:indoor )?pool|indoor pool|piscine (?:couverte|chauffee)|"
    r"hallenbad|overdekt zwembad|verwarmd zwembad|piscina (?:coperta|riscaldata)",
    "playground": r"parque infantil|zona infantil|playground|aire de jeux|spielplatz|speeltuin|parco giochi|area giochi",
    "kids_club": r"mini ?club|kids ?club|club infantil|club enfants|kinderclub|club bambini",
    "entertainment": r"animacion|entertainment|\banimation\b|animatie|animazione",
    "sports_ground": r"pista (?:polideportiva|deportiva)|multi-?sport|campo de futbol|voleibol|volleyball|baloncesto|"
    r"sports? (?:ground|field|court)|terrain de sport|sportplatz|sportveld|campo sportivo|petanca|petanque",
    "tennis": r"\btenis\b|\btennis\b|\bpadel\b",
    "gym": r"gimnasio|\bgym\b|fitness|salle de sport|palestra",
    "spa": r"\bspa\b|wellness|jacuzzi|sauna|hidromasaje",
    "games_room": r"sala de juegos|games? room|salle de jeux|spielraum|speelzaal|sala giochi|billar|ping[- ]?pong",
    "bike_rental": r"alquiler de bicicletas|bike (?:rental|hire)|location de velos?|fahrradverleih|fietsverhuur|"
    r"noleggio (?:bici|biciclette)",
    "water_sports": r"kayak|piraguismo|canoa|paddle ?surf|deportes nauticos|water ?sports|sports nautiques|"
    r"wassersport|watersport|sport acquatici|windsurf|buceo|snorkel",
    "bbq": r"barbacoas?|\bbbq\b|barbecue|\bgrill\b|braai",
    "hot_showers": r"agua caliente|duchas? calientes?|hot showers?|douches? chaudes?|warmwasser|warme douches?|docce calde",
    "toilets": r"sanitarios|bloques? sanitarios?|\baseos\b|\btoilets?\b|sanitaires|sanitar|toiletgebouw|servizi igienici",
    "accessible": r"movilidad reducida|minusvalid|discapacidad|accesibles?|wheelchair|accessible|\bpmr\b|barrierefrei|"
    r"rolstoel|disabili",
    "baby_room": r"cambiador|sala de bebes|bano de bebes|baby[- ]?(?:room|changing)|salle de bebe|wickelraum|babyruimte|"
    r"fasciatoio",
    "dishwashing": r"fregaderos|lavaderos|dishwashing|washing[- ]up|\bplonge\b|abwasch|afwasplaats|lavastoviglie",
    "electricity": r"electricidad|toma de corriente|electricity|electrical hook|electricite|branchement electrique|"
    r"\bstrom\b|elektriciteit|stroomaansluiting|elettricita",
    "water_points": r"agua potable|puntos de agua|drinking water|eau potable|trinkwasser|drinkwater|acqua potabile",
    "motorhome_service": r"autocaravanas|motorhome service|aire de service|borne camping-car|ver- und entsorgung|"
    r"camper ?service|area di sosta camper",
    "chemical_disposal": r"(?:wc|vaciado) quimico|chemical (?:toilet )?disposal|vidange|chemietoilette|chemisch toilet|"
    r"wc chimico",
    "shade": r"\bsombra\b|\bshaded?\b|ombrag|schattig|schaduw|ombreggiat",
    "parking": r"aparcamiento|\bparking\b|parkplatz|parkeerplaats|parcheggio",
    "ev_charging": r"punto de recarga|recarga (?:de )?vehiculos electricos|ev charging|electric (?:car|vehicle) charging|"
    r"borne de recharge|ladestation|laadpaal|colonnina",
    "pets": r"admiten (?:perros|mascotas|animales)|mascotas bienvenidas|pet[- ]?friendly|pets (?:are )?(?:welcome|allowed)|"
    r"animaux (?:acceptes|admis|bienvenus)|hunde (?:erlaubt|willkommen)|huisdieren (?:toegestaan|welkom)|"
    r"animali (?:ammessi|benvenuti)|dog[- ]friendly",
    "dog_area": r"zona (?:para )?perros|parque (?:para )?perros|dog (?:park|shower|area)|espace chiens?|hundedusche|"
    r"hondenweide|area cani",
    "beach": r"\bplayas?\b|\bbeach\b|\bplages?\b|\bstrand\b|\bspiaggia\b",
    "river": r"\brio\b|\briver\b|\blago\b|\blake\b|\briviere\b|\bfluss\b|\brivier\b|\bfiume\b|embalse|pantano",
    "mountain": r"montana|pirineo|pyrenees|\bsierra\b|mountains?|montagnes?|gebirge|\bbergen\b|montagna|dolomit",
    "hiking": r"senderismo|rutas a pie|hiking|walking trails|randonnee|wanderwege|\bwandern\b|wandelroutes|"
    r"escursioni|trekking",
    "town": r"cerca del (?:pueblo|centro)|junto al pueblo|close to the (?:town|village)|pres du (?:village|centre)|"
    r"nahe dem (?:dorf|zentrum)|vicino al (?:paese|centro)",
    "public_transport": r"parada de autobus|bus stop|transporte publico|public transport|arret de bus|"
    r"bushaltestelle|bushalte|fermata dell'autobus",
}
FACILITY_PATTERNS = {key: re.compile(pattern, re.IGNORECASE) for key, pattern in FACILITY_KEYWORDS.items()}

CHECK_IN = re.compile(
    r"(?:check[- ]?in|entrada|llegadas?|arrivees?|arrivals?|arrival|anreise|aankomst|arrivo|arrivi)"
    r"[^0-9\n]{0,40}?(?:a partir de |desde |from |des |ab |vanaf |dalle )?([0-2]?\d)[:.h]([0-5]\d)",
    re.IGNORECASE,
)
CHECK_OUT = re.compile(
    r"(?:check[- ]?out|salidas?|departs?|departures?|abreise|vertrek|partenza|partenze)"
    r"[^0-9\n]{0,40}?([0-2]?\d)[:.h]([0-5]\d)",
    re.IGNORECASE,
)
ALL_YEAR = re.compile(
    r"abierto todo el ano|abierto (?:los )?365 dias|open all year|open (?:all )?year[- ]round|ouvert toute l'annee|"
    r"ganzjahrig geoffnet|het hele jaar (?:geopend|open)|aperto tutto l'anno",
    re.IGNORECASE,
)
OPENING_WORDS = re.compile(r"abierto|apertura|open|opening|ouvert|ouverture|geoffnet|geopend|aperto", re.IGNORECASE)
STARS = re.compile(
    r"camping[^.\n]{0,40}?\b([1-5])\s*(?:estrellas|stars?|etoiles|sterne|sterren|stelle)\b|"
    r"\b([1-5])[- ]?(?:estrellas|stars?|etoiles|sterne|sterren|stelle)\b[^.\n]{0,20}camping",
    re.IGNORECASE,
)
MAP_PATTERNS = [
    re.compile(r"@(-?\d{1,2}\.\d{3,}),(-?\d{1,3}\.\d{3,})"),
    re.compile(r"!3d(-?\d{1,2}\.\d{3,})!4d(-?\d{1,3}\.\d{3,})"),
    re.compile(r"[?&](?:q|ll|center|query|destination|daddr)=(-?\d{1,2}\.\d{3,})(?:,|%2C)\s*(-?\d{1,3}\.\d{3,})"),
    re.compile(r"mlat=(-?\d{1,2}\.\d{3,}).*?mlon=(-?\d{1,3}\.\d{3,})"),
    re.compile(r"#map=\d+/(-?\d{1,2}\.\d{3,})/(-?\d{1,3}\.\d{3,})"),
]
MAP_EMBED_LNG_LAT = re.compile(r"!2d(-?\d{1,3}\.\d{3,})!3d(-?\d{1,2}\.\d{3,})")
POSTAL_LINE = re.compile(
    r"^(?:(?P<street>.{4,80}?)[,\s-]+)?(?P<cp>\d{5})[,\s]+(?P<city>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’. -]{1,40}?)"
    r"(?:\s*[(,-]\s*(?P<region>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’. -]{1,30})\)?)?\s*(?:[,.-]\s*(?:spain|espana|españa|france))?$",
    re.IGNORECASE,
)
STREET_WORDS = re.compile(
    r"\b(?:c/|calle|avda|avenida|av\.|carretera|ctra|camino|cami|paseo|passeig|plaza|placa|partida|paraje|finca|km|"
    r"carrer|rambla|ruta|urbanizacion|lugar|rue|route|chemin|avenue|strasse|straße|weg|via|viale|localita|road|street)\b",
    re.IGNORECASE,
)


@dataclass
class Page:
    url: str
    soup: BeautifulSoup
    role: str = "other"
    language: str | None = None
    _text: str | None = field(default=None, repr=False)

    @classmethod
    def from_html(cls, url, html, role="other", charset=None):
        """``html`` may be bytes: the encoding is then detected (header, <meta charset>...)."""
        if isinstance(html, bytes):
            soup = BeautifulSoup(html, "html.parser", from_encoding=charset)
        else:
            soup = BeautifulSoup(html, "html.parser")
        lang = None
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            lang = html_tag["lang"].split("-")[0].split("_")[0].lower()[:2] or None
        base = soup.find("base", href=True)
        if base and base["href"].strip():
            url = urljoin(url, base["href"].strip())
        return cls(url=url, soup=soup, role=role, language=lang)

    @property
    def text(self):
        """Visible text, one block per line."""
        if self._text is None:
            soup = copy.copy(self.soup)
            for tag in soup(["script", "style", "noscript", "template", "svg"]):
                tag.decompose()
            self._text = "\n".join(clean(line) for line in soup.get_text("\n").splitlines() if clean(line))
        return self._text

    def absolute(self, url):
        return urljoin(self.url, url.strip()) if url else ""


def _safe(function, default=None):
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:  # noqa: BLE001 - one broken website detail must not stop the import
            logger.warning("Import extractor %s failed", function.__name__, exc_info=True)
            return default

    return wrapper


# --- Structured data -------------------------------------------------------------


def json_ld(page):
    objects = []
    for script in page.soup.find_all("script", type=lambda value: value and "ld+json" in value.lower()):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except ValueError:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
            except ValueError:
                continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop(0)
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                if "@graph" in item:
                    stack.extend(item["@graph"] if isinstance(item["@graph"], list) else [item["@graph"]])
                objects.append(item)
    return objects


def types_of(obj):
    kind = obj.get("@type") or []
    kinds = kind if isinstance(kind, list) else [kind]
    return {str(value).lower().rsplit("/", 1)[-1] for value in kinds}


def _value(value):
    if isinstance(value, dict):
        return value.get("url") or value.get("@id") or value.get("name") or value.get("contentUrl")
    if isinstance(value, list):
        return _value(value[0]) if value else None
    return value


def business_objects(pages):
    found = []
    for page in pages:
        for obj in json_ld(page):
            kinds = types_of(obj)
            if kinds & CAMPING_TYPES:
                found.insert(0, obj)
            elif kinds & BUSINESS_TYPES:
                found.append(obj)
    return found


def meta(page, *names):
    for name in names:
        tag = page.soup.find("meta", attrs={"property": name}) or page.soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return clean(tag["content"])
    return ""


# --- Name and texts ----------------------------------------------------------------


def camping_name(pages, objects):
    home = pages[0]
    for obj in objects:
        name = clean(str(_value(obj.get("name")) or ""))
        if name and len(name) <= 120:
            return name
    site_name = meta(home, "og:site_name", "application-name")
    if site_name:
        return site_name
    title = clean(home.soup.title.get_text()) if home.soup.title else ""
    if title:
        parts = [clean(part) for part in re.split(r"\s[|\-–—·:]\s|\s\|\s?", title) if clean(part)]
        for part in parts:
            if "camping" in fold(part) or "campsite" in fold(part):
                return part[:120]
        if parts:
            return parts[0][:120]
    heading = home.soup.find("h1")
    return clean(heading.get_text())[:120] if heading else ""


def _content_soup(page):
    soup = copy.copy(page.soup)
    for tag in soup(["script", "style", "noscript", "template", "svg", "nav", "header", "footer", "form", "aside"]):
        tag.decompose()
    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue
        marker = " ".join(tag.get("class", []) or []) + " " + (tag.get("id") or "")
        if marker.strip() and NOISE.search(marker):
            tag.decompose()
    return soup


def paragraphs(page, limit=6, max_chars=1400):
    found, total = [], 0
    for tag in _content_soup(page).find_all(["p", "li"]):
        text = clean(tag.get_text(" "))
        if len(text) < 70 or LEGAL_TEXT.search(text) or text in found:
            continue
        links = sum(len(clean(a.get_text())) for a in tag.find_all("a"))
        if links > len(text) / 2:
            continue
        found.append(text)
        total += len(text)
        if len(found) >= limit or total >= max_chars:
            break
    return found


def texts_for(page, objects=()):
    description = ""
    for obj in objects:
        value = obj.get("description")
        if isinstance(value, str) and len(clean(value)) >= 80:
            description = clean(value)
            break
    meta_description = meta(page, "description", "og:description", "twitter:description")
    body = paragraphs(page)
    if body and (not description or len("\n\n".join(body)) > len(description)):
        description = "\n\n".join(body)
    if not description:
        description = meta_description
    tagline = first_sentence(meta_description) if meta_description else ""
    if tagline and description.startswith(tagline.rstrip("…")):
        tagline = ""
    return {"tagline": tagline, "description": description}


# --- Contact -------------------------------------------------------------------------


def _phone_digits(value):
    value = unquote(value or "")
    plus = value.strip().startswith("+") or value.strip().startswith("00")
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00"):
        digits = digits[2:]
    return ("+" if plus else "") + digits


def _readable_phone(link_text, href_value):
    text = clean(link_text)
    if len(re.sub(r"\D", "", text)) >= 9 and len(text) <= 25 and not re.search(r"[a-z]{3}", text, re.I):
        return text
    return _phone_digits(href_value)


def contacts(pages):
    emails, phones, whatsapp, instagram, facebook = Counter(), Counter(), Counter(), Counter(), Counter()
    for page in pages:
        weight = 2 if page.role in ("home", "contact") else 1
        for link in page.soup.find_all("a", href=True):
            href = link["href"].strip()
            low = href.lower()
            if low.startswith("mailto:"):
                address = unquote(href[7:].split("?")[0]).strip()
                if EMAIL.fullmatch(address):
                    emails[address.lower()] += weight
            elif low.startswith("tel:"):
                phone = _readable_phone(link.get_text(), href[4:])
                if len(re.sub(r"\D", "", phone)) >= 9:
                    phones[phone] += weight
            elif "wa.me/" in low or "whatsapp.com/send" in low or low.startswith("whatsapp:"):
                number = ""
                if "wa.me/" in low:
                    number = low.split("wa.me/", 1)[1].split("?")[0]
                else:
                    number = (parse_qs(urlsplit(href).query).get("phone") or [""])[0]
                digits = re.sub(r"\D", "", number)
                if len(digits) >= 9:
                    whatsapp[f"+{digits}"] += weight
            elif "instagram.com/" in low:
                handle = urlsplit(href).path.strip("/").split("/")[0]
                if handle and handle not in ("p", "reel", "explore", "stories", "accounts", "share"):
                    instagram[f"https://www.instagram.com/{handle}/"] += weight
            elif "facebook.com/" in low and not re.search(r"sharer|share\.php|/share|dialog|plugins|/tr\?|login", low):
                parts = urlsplit(href)
                path = parts.path.strip("/")
                if path == "profile.php" and parts.query:
                    facebook[f"https://www.facebook.com/profile.php?{parts.query}"] += weight
                elif path and not path.startswith(("sharer", "watch", "events", "groups/")):
                    facebook[f"https://www.facebook.com/{path}/"] += weight
    if not emails:
        for page in pages:
            for address in EMAIL.findall(page.text):
                if not address.lower().endswith(IMAGE_EXTENSIONS + (".gif", ".svg")):
                    emails[address.lower()] += 1
    if not phones:
        for page in pages:
            for match in re.finditer(
                r"(?:tel[eé]?f?o?n?o?|phone|t[ée]l|telefon|telefono|tlf|tfno)\.?\s*[:.]?\s*(\+?[\d][\d\s().-]{7,18}\d)",
                page.text,
                re.IGNORECASE,
            ):
                phones[clean(match.group(1))] += 1
    return {
        "email": emails.most_common(1)[0][0] if emails else "",
        "phone": phones.most_common(1)[0][0] if phones else "",
        "whatsapp": whatsapp.most_common(1)[0][0] if whatsapp else "",
        "instagram": instagram.most_common(1)[0][0] if instagram else "",
        "facebook": facebook.most_common(1)[0][0] if facebook else "",
    }


# --- Address and map ------------------------------------------------------------------


def _country_name(value):
    value = clean(str(_value(value) or ""))
    return COUNTRIES.get(value.lower(), value)


def address(pages, objects, phone=""):
    result = {}
    for obj in objects:
        raw = obj.get("address")
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if isinstance(raw, dict):
            result = {
                "address": clean(str(raw.get("streetAddress") or "")),
                "postal_code": clean(str(raw.get("postalCode") or "")),
                "city": clean(str(raw.get("addressLocality") or "")),
                "region": clean(str(raw.get("addressRegion") or "")),
                "country": _country_name(raw.get("addressCountry")),
            }
            break
        if isinstance(raw, str) and raw.strip():
            result = {"address": clean(raw)}
            break
    if not result.get("postal_code"):
        for page in pages:
            tags = {
                prop: page.soup.find(attrs={"itemprop": prop})
                for prop in ("streetAddress", "postalCode", "addressLocality", "addressRegion")
            }
            if tags["postalCode"] or tags["addressLocality"]:
                result = {
                    "address": clean(tags["streetAddress"].get_text()) if tags["streetAddress"] else "",
                    "postal_code": clean(tags["postalCode"].get_text()) if tags["postalCode"] else "",
                    "city": clean(tags["addressLocality"].get_text()) if tags["addressLocality"] else "",
                    "region": clean(tags["addressRegion"].get_text()) if tags["addressRegion"] else "",
                    **({"country": result["country"]} if result.get("country") else {}),
                }
                break
    if not result.get("postal_code"):
        for page in sorted(pages, key=lambda item: item.role != "contact"):
            for line in page.text.splitlines():
                if len(line) > 140 or not re.search(r"\b\d{5}\b", line) or "@" in line:
                    continue
                match = POSTAL_LINE.match(line.strip(" ·|"))
                if match is None:
                    continue
                street = clean(match.group("street") or "")
                if street and not STREET_WORDS.search(street):
                    street = ""
                result = {
                    "address": street.strip(" ,-"),
                    "postal_code": match.group("cp"),
                    "city": clean(match.group("city")).strip(" ,.-"),
                    "region": clean(match.group("region") or "").strip(" ,.-"),
                    **({"country": result["country"]} if result.get("country") else {}),
                }
                break
            if result.get("postal_code"):
                break
    if not result.get("country") and phone.startswith("+"):
        digits = phone[1:].replace(" ", "")
        for prefix in sorted(PHONE_PREFIX_COUNTRY, key=len, reverse=True):
            if digits.startswith(prefix):
                result["country"] = PHONE_PREFIX_COUNTRY[prefix]
                break
    return {key: value for key, value in result.items() if value}


def _valid_coordinates(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if -90 <= lat <= 90 and -180 <= lng <= 180 and (abs(lat) > 0.01 or abs(lng) > 0.01):
        return round(lat, 6), round(lng, 6)
    return None


def coordinates(pages, objects):
    for obj in objects:
        geo = obj.get("geo")
        if isinstance(geo, dict):
            found = _valid_coordinates(geo.get("latitude"), geo.get("longitude"))
            if found:
                return found
    for page in pages:
        position = meta(page, "geo.position", "ICBM")
        if position:
            parts = re.split(r"[;,]\s*", position)
            if len(parts) == 2 and (found := _valid_coordinates(*parts)):
                return found
        lat = meta(page, "place:location:latitude", "og:latitude")
        lng = meta(page, "place:location:longitude", "og:longitude")
        if lat and lng and (found := _valid_coordinates(lat, lng)):
            return found
    for page in pages:
        for tag in page.soup.find_all(["iframe", "a", "div"]):
            source = unquote(tag.get("src") or tag.get("href") or tag.get("data-src") or "")
            if not source or not re.search(r"maps|openstreetmap|osm|map", source, re.I):
                continue
            match = MAP_EMBED_LNG_LAT.search(source)
            if match and (found := _valid_coordinates(match.group(2), match.group(1))):
                return found
            for pattern in MAP_PATTERNS:
                match = pattern.search(source)
                if match and (found := _valid_coordinates(match.group(1), match.group(2))):
                    return found
        for tag in page.soup.find_all(attrs={"data-lat": True, "data-lng": True}):
            if found := _valid_coordinates(tag["data-lat"], tag["data-lng"]):
                return found
    return None


# --- Images ------------------------------------------------------------------------


def _from_srcset(value):
    best, best_size = None, -1
    for candidate in (value or "").split(","):
        parts = candidate.strip().split()
        if not parts:
            continue
        size = 0
        if len(parts) > 1:
            descriptor = parts[1]
            number = re.sub(r"[^\d.]", "", descriptor) or "0"
            size = float(number) * (1000 if descriptor.endswith("x") else 1)
        if size > best_size:
            best, best_size = parts[0], size
    return best, best_size


def _image_url(tag):
    for attr in ("data-srcset", "data-lazy-srcset", "srcset"):
        if tag.get(attr):
            url, size = _from_srcset(tag[attr])
            if url:
                return url, size
    for attr in ("data-src", "data-lazy-src", "data-original", "data-bg", "data-large_image", "src"):
        value = tag.get(attr)
        if value and not value.startswith("data:"):
            return value, 0
    return None, 0


def _usable_image(url):
    path = urlsplit(url).path.lower()
    if not path.endswith(IMAGE_EXTENSIONS) and "/image" not in path and "format=" not in url:
        return False
    return not SKIP_IMAGE.search(path.rsplit("/", 1)[-1])


def original_image(url):
    """WordPress keeps the original next to its resized copies (photo-300x200.jpg)."""
    return WP_SIZE.sub("", url)


def logo_url(pages, objects):
    for obj in objects:
        value = _value(obj.get("logo"))
        if isinstance(value, str) and value.strip():
            return pages[0].absolute(value)
    home = pages[0]
    for tag in home.soup.find_all("img"):
        marker = " ".join(
            [" ".join(tag.get("class", []) or []), tag.get("id") or "", tag.get("alt") or "", tag.get("src") or ""]
        )
        parent_marker = " ".join(
            " ".join(parent.get("class", []) or []) + " " + (parent.get("id") or "")
            for parent in tag.parents
            if parent.name
        )[:400]
        if re.search(r"logo", marker, re.I) or re.search(
            r"\blogo|site-branding|navbar-brand|brand", parent_marker, re.I
        ):
            url, _size = _image_url(tag)
            if url:
                return home.absolute(url)
    for link in home.soup.find_all("link", rel=True):
        rels = " ".join(link["rel"]).lower()
        if "apple-touch-icon" in rels and link.get("href"):
            return home.absolute(link["href"])
    return ""


def photos(pages, name="", limit=40):
    """Candidate photos, best first: ``[{url, alt, score}]``."""
    candidates = {}
    folded_name = fold(name)

    def add(url, score, alt="", page=None):
        if not url or url.startswith("data:"):
            return
        url = page.absolute(url) if page else url
        if not url.startswith(("http://", "https://")) or not _usable_image(url):
            return
        key = original_image(urlsplit(url)._replace(query="", fragment="").geturl())
        alt = clean(alt)
        if fold(alt) == folded_name or len(alt) < 4 or re.fullmatch(r"[\w-]+\.(jpe?g|png|webp)", alt, re.I):
            alt = ""
        entry = candidates.get(key)
        if entry is None:
            candidates[key] = {
                "url": url,
                "alt": alt,
                "score": score,
                "original": original_image(url),
                "lang": page.language if page else None,
            }
        else:
            entry["score"] += score / 2
            if WP_SIZE.search(entry["url"]) and not WP_SIZE.search(url):
                entry["url"] = url
            if alt and not entry["alt"]:
                entry["alt"], entry["lang"] = alt, page.language if page else None

    for page in pages:
        bonus = 2 if page.role in ("gallery", "accommodation") else 0
        for key in ("og:image", "twitter:image"):
            value = meta(page, key)
            if value:
                add(value, 6 + bonus, page=page)
        for obj in json_ld(page):
            images = obj.get("image")
            for image in images if isinstance(images, list) else [images]:
                value = _value(image)
                if isinstance(value, str):
                    add(value, 4, page=page)
        for link in page.soup.find_all("a", href=True):
            href = link["href"]
            if urlsplit(href).path.lower().endswith(IMAGE_EXTENSIONS):
                image = link.find("img")
                add(href, 5 + bonus, alt=image.get("alt", "") if image else link.get("title", ""), page=page)
        for tag in page.soup.find_all(["img", "source"]):
            url, size = _image_url(tag)
            if not url:
                continue
            width = tag.get("width") or ""
            height = tag.get("height") or ""
            if width.isdigit() and height.isdigit() and max(int(width), int(height)) < 300:
                continue
            ancestors = " ".join(
                " ".join(parent.get("class", []) or []) for parent in list(tag.parents)[:4] if parent.name
            )
            if re.search(r"logo|icon|footer|partner|sponsor|payment", ancestors, re.I):
                continue
            score = 1 + bonus
            if GALLERY_HINT.search(ancestors):
                score += 3
            if size >= 1000 or (width.isdigit() and int(width) >= 800):
                score += 2
            add(url, score, alt=tag.get("alt", ""), page=page)
        for tag in page.soup.find_all(style=re.compile(r"background(?:-image)?\s*:[^;]*url\(", re.I)):
            match = re.search(r"url\((['\"]?)([^'\")]+)\1\)", tag["style"])
            if match:
                add(match.group(2), 3 + bonus, page=page)
    ranked = sorted(candidates.values(), key=lambda item: -item["score"])
    return ranked[:limit]


# --- Facilities, times, opening, stars -----------------------------------------------


def facilities(pages):
    found = {}
    for page in pages:
        text = fold(page.text)
        for key, pattern in FACILITY_PATTERNS.items():
            if key in found:
                continue
            match = pattern.search(text)
            if match:
                start = max(match.start() - 40, 0)
                found[key] = clean(text[start : match.end() + 40])
    return found


def _time(match):
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23:
        return ""
    return f"{hour:02d}:{minute:02d}"


def check_times(pages, objects):
    result = {}
    for obj in objects:
        for key, field_name in (("checkinTime", "check_in_from"), ("checkoutTime", "check_out_until")):
            value = obj.get(key)
            if isinstance(value, str) and (match := re.search(r"([0-2]?\d):([0-5]\d)", value)):
                result[field_name] = _time(match)
    for page in pages:
        text = fold(page.text)
        if "check_in_from" not in result and (match := CHECK_IN.search(text)):
            result["check_in_from"] = _time(match)
        if "check_out_until" not in result and (match := CHECK_OUT.search(text)):
            result["check_out_until"] = _time(match)
    return {key: value for key, value in result.items() if value}


def opening(pages, today):
    for page in pages:
        text = fold(page.text)
        if ALL_YEAR.search(text):
            return {"open_all_year": True}
    for page in pages:
        for line in fold(page.text).splitlines():
            if not OPENING_WORDS.search(line) or len(line) > 300:
                continue
            for start, end in dates.find_periods(line, today):
                if (end - start).days >= 60:
                    return {"opening_date": start.isoformat(), "closing_date": end.isoformat()}
    return {}


def stars(pages, objects):
    for obj in objects:
        rating = obj.get("starRating")
        value = _value(rating.get("ratingValue")) if isinstance(rating, dict) else None
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            continue
        if 1 <= number <= 5:
            return number
    for page in pages:
        match = STARS.search(fold(page.text))
        if match:
            return int(match.group(1) or match.group(2))
    return None


TAX_ID = re.compile(
    r"\b(?:n\.?\s?i\.?\s?f\.?|c\.?\s?i\.?\s?f\.?|nie|vat(?: number| no\.?)?|tva|ust-?idnr\.?|p\.?\s?iva|partita iva|"
    r"btw(?:-nummer)?|siret|siren)\s*[:.º°-]*\s*((?:[a-z]{2} ?)?[a-z0-9](?:[-.]?[a-z0-9]){6,13})\b",
    re.IGNORECASE,
)
LEGAL_NAME = re.compile(
    r"(?:titular(?: del sitio web| de la web)?|raz[oó]n social|denominaci[oó]n(?: social)?|empresa titular|company name|"
    r"owner|raison sociale|firmenname|bedrijfsnaam|ragione sociale)\s*[:.-]\s*([^\n;|]{3,120})",
    re.IGNORECASE,
)
COMPANY = re.compile(
    r"\b([A-ZÀ-Ý][\w&'’.-]*(?:\s+[\w&'’.-]+){0,6}?,?\s+(?:S\.\s?L\.(?:\s?U\.)?|S\.\s?A\.|S\.\s?C\.\s?P\.|C\.\s?B\.|"
    r"SL|SLU|SA|SARL|SAS|GmbH|B\.V\.|S\.r\.l\.))(?=[\s,.;)]|$)"
)
REGISTRY = re.compile(
    r"registro mercantil|registre mercantil|commercial regist|rcs |handelsregister|kamer van koophandel|\bkvk\b|"
    r"registro delle imprese",
    re.IGNORECASE,
)
TOURISM_ID = re.compile(
    r"(?:registro (?:general )?de (?:empresas |establecimientos )?(?:y actividades )?tur[ií]stic\w*|"
    r"reg(?:istro)?\.?\s*(?:de\s+)?tur[ií]s(?:mo|tico)|n[.ºo°]*\s*(?:de )?registro(?: tur[ií]stico)?|"
    r"n[uú]mero de registro|signatura)\s*[:.-]?\s*"
    r"([A-Z]{1,4}[-/ ]?\d[\dA-Z/.-]{2,15})",
    re.IGNORECASE,
)
CATALAN_TOURISM_ID = re.compile(r"\b(K[GBTL]-\d{3,6})\b")
GA_ID = re.compile(r"(?:gtag\(\s*['\"]config['\"]\s*,\s*['\"]|googletagmanager\.com/gtag/js\?id=)(G-[A-Z0-9]{4,16})")


def legal_details(pages):
    """Owner, tax ID and registrations (legal notice), plus Google Analytics / Search Console codes."""
    result = {}
    ordered = sorted(pages, key=lambda page: page.role != "legal")
    for page in ordered:
        text = page.text
        if "tax_id" not in result and (match := TAX_ID.search(text)):
            value = re.sub(r"[\s.]", "", match.group(1)).upper()
            if 8 <= len(value.replace("-", "")) <= 15 and re.search(r"\d{5}", value):
                result["tax_id"] = value
        if "legal_name" not in result and page.role == "legal":
            match = LEGAL_NAME.search(text) or COMPANY.search(text)
            if match:
                name = clean(match.group(1)).strip(" ,;:")
                if name.endswith(".") and not re.search(r"\b[A-Z]\.$", name):
                    name = name[:-1]  # end of sentence, not "S.L."
                if 3 <= len(name) <= 120 and not EMAIL.search(name):
                    result["legal_name"] = name
        if "registry_info" not in result and page.role == "legal":
            for line in text.splitlines():
                if REGISTRY.search(line) and len(line) <= 300:
                    result["registry_info"] = clean(line).strip(" .")
                    break
        if "tourism_registration" not in result:
            match = TOURISM_ID.search(text) or CATALAN_TOURISM_ID.search(text)
            if match:
                result["tourism_registration"] = clean(match.group(1)).strip(" .")
    if "legal_name" not in result:
        for page in pages:
            footer = page.soup.find("footer")
            match = COMPANY.search(clean(footer.get_text(" "))) if footer else None
            if match:
                result["legal_name"] = clean(match.group(1))
                break
    home = pages[0]
    for script in home.soup.find_all("script"):
        match = GA_ID.search((script.get("src") or "") + " " + (script.string or ""))
        if match:
            result["ga_measurement_id"] = match.group(1)
            break
    verification = home.soup.find("meta", attrs={"name": "google-site-verification"})
    if verification and verification.get("content"):
        code = clean(verification["content"])
        if re.fullmatch(r"[A-Za-z0-9_-]{10,100}", code):
            result["search_console_verification"] = code
    return result


def language_alternates(page):
    """``{language: url}`` of the same page in other languages (hreflang)."""
    found = {}
    for link in page.soup.find_all("link", hreflang=True, href=True):
        code = link["hreflang"].split("-")[0].lower()
        if code and code != "x" and code not in found:
            found[code] = page.absolute(link["href"])
    return found


contacts = _safe(contacts, {})
address = _safe(address, {})
coordinates = _safe(coordinates)
logo_url = _safe(logo_url, "")
photos = _safe(photos, [])
facilities = _safe(facilities, {})
check_times = _safe(check_times, {})
opening = _safe(opening, {})
stars = _safe(stars)
legal_details = _safe(legal_details, {})
texts_for = _safe(texts_for, {"tagline": "", "description": ""})
camping_name = _safe(camping_name, "")
