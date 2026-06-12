"""Heuristic resolution of extraction mode for the 'Let ScrapeGPT decide' option.

When the user does not explicitly choose STRUCTURED or CONTENT at analyze time,
the mode must still be decided *before* analysis runs, because ``extraction_mode``
selects which analysis schema the analyzer requests (it is fixed at project
creation). Rather than silently defaulting every "decide" submission to
STRUCTURED, this module makes a cheap, transparent guess from the URL alone:
content-like destinations (code repositories, docs sites, articles, blogs,
wikis) lean CONTENT; everything else defaults to STRUCTURED.

This is intentionally a low-confidence heuristic. Analysis can still surface
warnings if the guess is wrong, and the user can re-create the project in the
other mode. It does not call the network or the LLM.
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

# Hosts whose pages are almost always prose/document content rather than
# row-like records. Matched on the exact host or any subdomain of it.
_CONTENT_HOST_HINTS = (
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "readthedocs.io",
    "readthedocs.org",
    "medium.com",
    "substack.com",
    "dev.to",
    "wikipedia.org",
    "stackoverflow.com",
)

# Path fragments that strongly suggest document/content pages.
_CONTENT_PATH_HINTS = (
    "/docs",
    "/doc/",
    "/documentation",
    "/blog",
    "/article",
    "/wiki",
    "/readme",
    "/guide",
    "/manual",
    "/knowledge",
    "/help/",
    "/posts/",
    "/post/",
    "/news/",
)

# File suffixes that are document content.
_CONTENT_SUFFIXES = (".md", ".rst", ".txt", ".adoc")


def infer_extraction_mode_from_url(url: str) -> str:
    """Guess ``"CONTENT"`` or ``"STRUCTURED"`` from the URL. Defaults to STRUCTURED.

    Pure and side-effect free; safe to call before any fetch.
    """
    try:
        parts = urlsplit(url.strip().lower())
    except (ValueError, AttributeError):
        return "STRUCTURED"

    host = parts.netloc.split("@")[-1].split(":")[0]
    path = parts.path

    if any(host == hint or host.endswith("." + hint) for hint in _CONTENT_HOST_HINTS):
        return "CONTENT"
    if path.endswith(_CONTENT_SUFFIXES):
        return "CONTENT"
    if any(hint in path for hint in _CONTENT_PATH_HINTS):
        return "CONTENT"
    return "STRUCTURED"


def resolve_extraction_mode(url: str, explicit: str | None) -> str:
    """Return the explicit mode when the user chose one, otherwise infer from the URL."""
    if explicit:
        return explicit
    return infer_extraction_mode_from_url(url)


def detect_alternate_mode(html: str, current_mode: str) -> str | None:
    """Heuristically detect whether the *other* extraction mode also has data.

    Returns the suggested alternate mode ("STRUCTURED" / "CONTENT") when the
    page meaningfully contains the other kind of data, else None. Used to offer
    the user a one-click sibling project for the same URL so they don't have to
    choose and lose one. Conservative by design — a suggestion, not a verdict.
    """
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return None

    # Structured signal: a real data table, or a large repeated container set
    # (a listing/grid sharing one class many times).
    class_counts: Counter[str] = Counter()
    for element in soup.find_all(["div", "li", "article", "section"]):
        for css_class in element.get("class") or []:
            class_counts[css_class] += 1
    max_repeat = max(class_counts.values(), default=0)
    big_tables = sum(1 for t in soup.find_all("table") if len(t.find_all("tr")) >= 3)
    has_structured = big_tables >= 1 or max_repeat >= 12

    # Content signal: substantial prose (paragraph text) or an <article>.
    paragraph_text = sum(
        len(p.get_text(" ", strip=True)) for p in soup.find_all("p")
    )
    has_content = paragraph_text >= 1200 or bool(soup.find("article"))

    mode = (current_mode or "").upper()
    if mode == "STRUCTURED" and has_content:
        return "CONTENT"
    if mode == "CONTENT" and has_structured:
        return "STRUCTURED"
    return None
