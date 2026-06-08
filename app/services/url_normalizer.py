"""URL normalization and same-site discovery helpers for project extraction."""

from __future__ import annotations

from fnmatch import fnmatch
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Resolve and normalize a crawl URL while preserving meaningful query params."""
    absolute = urljoin(base_url or "", url)
    parsed = urlparse(absolute)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(query_items, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def same_origin(url: str, root_url: str) -> bool:
    parsed = urlparse(url)
    root = urlparse(root_url)
    return parsed.scheme.lower() == root.scheme.lower() and parsed.netloc.lower() == root.netloc.lower()


def _matches_patterns(url: str, patterns: list[dict] | None) -> bool:
    """Apply optional include/exclude glob patterns from an extraction spec."""
    if not patterns:
        return True

    includes: list[str] = []
    excludes: list[str] = []
    for item in patterns:
        pattern = item.get("pattern") or item.get("glob")
        if not pattern:
            continue
        kind = str(item.get("type") or item.get("mode") or "include").lower()
        if kind == "exclude":
            excludes.append(str(pattern))
        else:
            includes.append(str(pattern))

    if any(fnmatch(url, pattern) for pattern in excludes):
        return False
    if includes and not any(fnmatch(url, pattern) for pattern in includes):
        return False
    return True


def discover_same_site_links(
    html: str,
    *,
    page_url: str,
    root_url: str,
    patterns: list[dict] | None = None,
    limit: int = 200,
) -> list[str]:
    """Return normalized same-origin links discovered in page order."""
    soup = BeautifulSoup(html, "lxml")
    found: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        normalized = normalize_url(href, page_url)
        if normalized in seen:
            continue
        if not same_origin(normalized, root_url):
            continue
        if not _matches_patterns(normalized, patterns):
            continue
        seen.add(normalized)
        found.append(normalized)
        if len(found) >= limit:
            break
    return found
