"""Download pages and images from a camping's current website, safely.

The URL comes from a user, so every request (and every redirect) is checked
to point to a public internet address: no localhost, private networks,
link-local or cloud metadata addresses. The connection goes to the checked
IP address itself, so a DNS answer cannot change between check and use.
"""

import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import urllib3
from django.conf import settings
from django.utils.translation import gettext as _

try:  # pragma: no cover - certifi is a dependency, the fallback is the system store
    import certifi

    CA_BUNDLE = certifi.where()
except ImportError:  # pragma: no cover
    CA_BUNDLE = None

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
ALLOWED_PORTS = {80, 443}
HTML_TYPES = ("text/html", "application/xhtml+xml")


class FetchError(Exception):
    """The page or image could not be downloaded (message for the user)."""


@dataclass
class Fetched:
    url: str
    status: int
    content_type: str
    charset: str | None
    content: bytes

    @property
    def is_html(self):
        return self.content_type in HTML_TYPES

    def text(self):
        for encoding in (self.charset, "utf-8", "cp1252"):
            if not encoding:
                continue
            try:
                return self.content.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        return self.content.decode("utf-8", errors="replace")


def user_agent():
    # Browser-like, because some hosting firewalls turn unknown bots away,
    # but saying who we are.
    name = settings.PLATFORM_NAME.replace(" ", "")
    contact = f"; +{settings.PLATFORM_URL}" if settings.PLATFORM_URL else ""
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36 "
        f"(compatible; {name}-Importer/1.0{contact})"
    )


def normalize_url(raw):
    """Add a scheme to what people type (``www.camping.com``) and validate it."""
    raw = (raw or "").strip()
    if not raw:
        raise FetchError(_("Enter the address of the website."))
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError(_("Enter a valid web address, e.g. https://www.mycamping.com."))
    return parts._replace(path=parts.path or "/").geturl()


def _public_addresses(host, port):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise FetchError(_("The address %(host)s could not be found.") % {"host": host}) from exc
    addresses = set()
    for _family, _type, _proto, _name, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0].split("%", 1)[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global and not settings.IMPORTER_ALLOW_PRIVATE_HOSTS:
            logger.warning("Blocked import request to %s (%s)", host, ip)
            raise FetchError(_("This address cannot be imported."))
        addresses.add((ip.version, str(ip)))  # IPv4 first
    if not addresses:
        raise FetchError(_("The address %(host)s could not be found.") % {"host": host})
    return [ip for _version, ip in sorted(addresses)]


def _open(url, accept, timeout):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError(_("The website redirected to an address that cannot be imported."))
    secure = parts.scheme == "https"
    port = parts.port or (443 if secure else 80)
    if port not in ALLOWED_PORTS and not settings.IMPORTER_ALLOW_PRIVATE_HOSTS:
        raise FetchError(_("This address cannot be imported."))
    host = parts.hostname
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    headers = {
        "Host": parts.netloc.rsplit("@", 1)[-1],
        "User-Agent": user_agent(),
        "Accept": accept,
        "Accept-Language": "es,en;q=0.8,fr;q=0.6,de;q=0.5,*;q=0.3",
        "Accept-Encoding": "gzip, deflate",
    }
    timeouts = urllib3.Timeout(connect=5, read=timeout)
    last_error = None
    for ip in _public_addresses(host, port):
        if secure:
            pool = urllib3.HTTPSConnectionPool(
                ip,
                port=port,
                timeout=timeouts,
                retries=False,
                maxsize=1,
                server_hostname=host,
                assert_hostname=host,
                cert_reqs="CERT_REQUIRED",
                ca_certs=CA_BUNDLE,
            )
        else:
            pool = urllib3.HTTPConnectionPool(ip, port=port, timeout=timeouts, retries=False, maxsize=1)
        try:
            return pool.urlopen(
                "GET",
                path,
                headers=headers,
                redirect=False,
                preload_content=False,
                decode_content=True,
                assert_same_host=False,
            )
        except urllib3.exceptions.SSLError as exc:
            raise FetchError(_("The secure connection with %(host)s failed.") % {"host": host}) from exc
        except urllib3.exceptions.HTTPError as exc:
            last_error = exc
    raise FetchError(_("%(host)s did not answer.") % {"host": host}) from last_error


def fetch(url, *, max_bytes, accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.5", timeout=10):
    """GET ``url`` following redirects; raises FetchError on any problem."""
    for _hop in range(MAX_REDIRECTS + 1):
        response = _open(url, accept, timeout)
        try:
            if response.status in (301, 302, 303, 307, 308) and response.headers.get("Location"):
                url = urljoin(url, response.headers["Location"])
                continue
            if response.status >= 400:
                raise FetchError(_("The website answered with an error (%(status)s).") % {"status": response.status})
            content_type, _sep, params = (response.headers.get("Content-Type") or "").partition(";")
            charset = None
            if "charset=" in params:
                charset = params.split("charset=", 1)[1].split(";")[0].strip().strip('"') or None
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > max_bytes:
                raise FetchError(_("The file is too large."))
            data = bytearray()
            try:
                for chunk in response.stream(64 * 1024):
                    data += chunk
                    if len(data) > max_bytes:
                        raise FetchError(_("The file is too large."))
            except urllib3.exceptions.HTTPError as exc:
                raise FetchError(_("The download was interrupted.")) from exc
            return Fetched(url, response.status, content_type.strip().lower(), charset, bytes(data))
        finally:
            response.release_conn()
    raise FetchError(_("The website redirects too many times."))
