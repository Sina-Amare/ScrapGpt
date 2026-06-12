"""Tests for the 'Let ScrapeGPT decide' extraction-mode heuristic."""

import pytest

from app.services.extraction_mode import (
    detect_alternate_mode,
    infer_extraction_mode_from_url,
    resolve_extraction_mode,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/anthropics/anthropic-sdk-python",
        "https://GitHub.com/owner/repo/blob/main/README.md",
        "https://example.readthedocs.io/en/latest/",
        "https://en.wikipedia.org/wiki/Web_scraping",
        "https://blog.example.com/posts/why-css-selectors",
        "https://example.com/docs/getting-started",
        "https://example.com/guide/setup",
        "https://example.com/notes.md",
    ],
)
def test_content_like_urls_infer_content(url: str) -> None:
    assert infer_extraction_mode_from_url(url) == "CONTENT"


@pytest.mark.parametrize(
    "url",
    [
        "https://shop.example.com/products?page=2",
        "https://example.com/listings/apartments",
        "https://directory.example.com/companies",
        "https://example.com/",
        "not a url",
        "",
    ],
)
def test_other_urls_default_to_structured(url: str) -> None:
    assert infer_extraction_mode_from_url(url) == "STRUCTURED"


def test_resolve_prefers_explicit_choice_over_heuristic() -> None:
    # An explicit choice always wins, even when the URL looks content-like.
    assert resolve_extraction_mode("https://github.com/owner/repo", "STRUCTURED") == "STRUCTURED"
    assert resolve_extraction_mode("https://shop.example.com/products", "CONTENT") == "CONTENT"


def test_resolve_falls_back_to_heuristic_when_unspecified() -> None:
    assert resolve_extraction_mode("https://github.com/owner/repo", None) == "CONTENT"
    assert resolve_extraction_mode("https://shop.example.com/products", None) == "STRUCTURED"
    assert resolve_extraction_mode("https://shop.example.com/products", "") == "STRUCTURED"


def test_detect_alternate_suggests_content_for_structured_with_prose() -> None:
    prose = "word " * 300  # ~1500 chars of paragraph text
    html = f"<html><body><table><tr><td>a</td></tr><tr><td>b</td></tr><tr><td>c</td></tr></table><p>{prose}</p></body></html>"
    assert detect_alternate_mode(html, "STRUCTURED") == "CONTENT"


def test_detect_alternate_suggests_structured_for_content_with_table() -> None:
    html = "<html><body><article><p>short</p></article><table><tr><td>1</td></tr><tr><td>2</td></tr><tr><td>3</td></tr></table></body></html>"
    assert detect_alternate_mode(html, "CONTENT") == "STRUCTURED"


def test_detect_alternate_none_when_only_current_kind_present() -> None:
    cards = "".join('<div class="card">item</div>' for _ in range(20))
    html = f"<html><body>{cards}</body></html>"
    # Structured project on a card grid with no prose -> nothing else to suggest.
    assert detect_alternate_mode(html, "STRUCTURED") is None


def test_detect_alternate_handles_empty_html() -> None:
    assert detect_alternate_mode("", "STRUCTURED") is None
