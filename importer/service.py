"""Read a camping's current website: pick the useful pages and extract everything."""

import logging
import re
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from . import extract
from .fetch import FetchError, fetch, normalize_url
from .models import SiteImport
from .prices import PriceCollector
from .text import fold

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_LINKED_PAGES = 8
ROLE_PATTERNS = {
    "prices": r"tarifa|precio|prices?|rates|tarif|preise|prijzen|prezzi|listino",
    "accommodation": r"alojamiento|bungalow|mobil|cabana|glamping|parcela|pitch|accommodation|hebergement|emplacement|"
    r"unterkunft|stellpl|accommodat|kampeerplaats|alloggi|piazzol|chalet|lodge",
    "facilities": r"instalaciones|servicios|services|facilities|equipements|einrichtungen|ausstattung|faciliteiten|"
    r"voorzieningen|servizi",
    "contact": r"contact|kontakt|contatti|situacion|ubicacion|como-llegar|localizacion|location|localisation|anfahrt|"
    r"ligging|route|dove",
    "gallery": r"galeria|galerie|gallery|fotos|photos|foto",
    "policies": r"condiciones|normas|reglamento|conditions|policies|policy|reglement|regeln|voorwaarden|regolamento",
}
ROLE_REGEXES = {role: re.compile(pattern, re.IGNORECASE) for role, pattern in ROLE_PATTERNS.items()}
ROLE_LIMITS = {"prices": 3, "accommodation": 2, "facilities": 1, "contact": 1, "gallery": 1, "policies": 1}
SKIP_LINKS = re.compile(
    r"\.(?:pdf|jpe?g|png|gif|webp|zip|docx?|xlsx?)$|wp-admin|wp-login|/feed|/tag/|/author/|/cart|/checkout|/carrito|"
    r"/cesta|/blog/|/noticias/|/news/|politica-de|privacy|cookies|aviso-legal|legal",
    re.IGNORECASE,
)
LANGUAGE_SEGMENT = re.compile(r"^/([a-z]{2})(?:[-_][a-z]{2})?(?:/|$)", re.IGNORECASE)


def _host(url):
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _language_of(url):
    match = LANGUAGE_SEGMENT.match(urlsplit(url).path)
    return match.group(1).lower() if match else None


def choose_links(home):
    """Links of the home page most likely to hold prices, accommodation, contact..."""
    candidates = {role: [] for role in ROLE_LIMITS}
    home_language = _language_of(home.url) or home.language
    for link in home.soup.find_all("a", href=True):
        url = home.absolute(link["href"]).split("#")[0]
        if not url.startswith(("http://", "https://")) or _host(url) != _host(home.url):
            continue
        if SKIP_LINKS.search(urlsplit(url).path) or url.rstrip("/") == home.url.rstrip("/"):
            continue
        link_language = _language_of(url)
        if link_language and home_language and link_language != home_language:
            continue
        label = fold(f"{link.get_text(' ')} {urlsplit(url).path}")
        for role, pattern in ROLE_REGEXES.items():
            if pattern.search(label) and url not in candidates[role]:
                candidates[role].append(url)
                break
    chosen, seen = [], set()
    for role, limit in ROLE_LIMITS.items():
        for url in candidates[role][:limit]:
            if url not in seen:
                seen.add(url)
                chosen.append((url, role))
    return chosen[:MAX_LINKED_PAGES]


def fetch_page(url, role):
    fetched = fetch(url, max_bytes=MAX_PAGE_BYTES, timeout=8)
    if not fetched.is_html:
        raise FetchError(_("The address is not a web page."))
    return extract.Page.from_html(fetched.url, fetched.content, role, charset=fetched.charset)


def _platform_language(code):
    codes = {code for code, _name in settings.LANGUAGES}
    return code if code in codes else None


def build_data(pages, alternates, today):
    """Everything found, as JSON-serialisable data for the review screen."""
    home = pages[0]
    objects = extract.business_objects(pages)
    language = _platform_language(home.language) or settings.LANGUAGE_CODE
    name = extract.camping_name(pages, objects)
    contact = extract.contacts(pages)
    coordinates = extract.coordinates(pages, objects)
    fields = {
        "name": name,
        **contact,
        **extract.address(pages, objects, contact.get("phone", "")),
        "stars": extract.stars(pages, objects),
        **extract.check_times(pages, objects),
        **extract.opening(pages, today),
    }
    if coordinates:
        fields["latitude"], fields["longitude"] = coordinates
    texts = {language: extract.texts_for(home, objects)}
    for code, page in alternates.items():
        found = extract.texts_for(page)
        if found.get("description") or found.get("tagline"):
            texts[code] = found
    location_info = {}
    for page in pages:
        if page.role == "contact":
            text = "\n\n".join(extract.paragraphs(page, limit=3, max_chars=800))
            if text:
                location_info[language] = text
            break
    prices = PriceCollector(today)
    for page in pages:
        prices.add_page(page)
    return {
        "language": language,
        "fields": {key: value for key, value in fields.items() if value not in (None, "", [], {})},
        "texts": {code: value for code, value in texts.items() if value.get("description") or value.get("tagline")},
        "location_info": location_info,
        "logo": extract.logo_url(pages, objects),
        "photos": extract.photos(pages, name),
        "facilities": extract.facilities(pages),
        **prices.result(),
        "pages": [{"url": page.url, "role": page.role} for page in pages]
        + [{"url": page.url, "role": f"language:{code}"} for code, page in alternates.items()],
    }


def run_import(camping, raw_url, user=None, today=None):
    """Download the website and store what was found (raises FetchError)."""
    today = today or timezone.localdate()
    deadline = time.monotonic() + settings.IMPORTER_TIME_BUDGET
    home = fetch_page(normalize_url(raw_url), "home")
    pages, warnings = [home], []
    for url, role in choose_links(home):
        if time.monotonic() > deadline - 4:
            warnings.append(_("Some pages were skipped to finish in time."))
            break
        try:
            pages.append(fetch_page(url, role))
        except FetchError as error:
            warnings.append(_("%(url)s could not be read: %(error)s") % {"url": url, "error": error})
    alternates = {}
    home_language = _platform_language(home.language)
    for code, url in extract.language_alternates(home).items():
        if not _platform_language(code) or code == home_language or url.rstrip("/") == home.url.rstrip("/"):
            continue
        if time.monotonic() > deadline - 4:
            break
        try:
            alternates[code] = fetch_page(url, "home")
        except FetchError:
            logger.info("Could not read the %s version of %s", code, home.url)
    data = build_data(pages, alternates, today)
    data["warnings"] = warnings
    return SiteImport.objects.create(camping=camping, url=home.url, data=data, created_by=user)
