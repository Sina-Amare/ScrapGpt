"""
Unit tests for scraper.scrape_url.

Uses a lightweight fake httpx client to avoid real network calls.
Tests cover: successful extraction with title, content truncation,
HTTP error codes, network timeouts, and non-content tag removal.
"""

import pytest
import httpx
from unittest.mock import MagicMock

from app.services.scraper import ScrapeError, scrape_url


# ---------------------------------------------------------------------------
# Fake httpx infrastructure
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, html: str, status_code: int = 200):
        self.text = html
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            mock_request = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = self.status_code
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=mock_request,
                response=mock_response,
            )


class FakeClient:
    """Async context manager mimicking httpx.AsyncClient."""

    def __init__(self, response: FakeResponse | None = None, raise_on_get=None):
        self._response = response
        self._raise_on_get = raise_on_get

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, url, **kwargs):
        if self._raise_on_get is not None:
            raise self._raise_on_get
        return self._response


def _patch_client(monkeypatch, fake: FakeClient):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake)


# ---------------------------------------------------------------------------
# Tests — success paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_url_extracts_title_and_body_text(monkeypatch):
    html = """
    <html>
      <head><title>Widget Guide</title></head>
      <body><main><p>Widgets are useful.</p></main></body>
    </html>
    """
    _patch_client(monkeypatch, FakeClient(FakeResponse(html)))

    content = await scrape_url("https://example.com")

    assert "Widget Guide" in content
    assert "Widgets are useful." in content


@pytest.mark.asyncio
async def test_scrape_url_removes_script_style_nav_footer(monkeypatch):
    html = """
    <html>
      <head><title>Clean</title></head>
      <body>
        <nav>Navigation menu</nav>
        <script>alert("xss")</script>
        <style>.hidden { display: none }</style>
        <footer>Footer text</footer>
        <p>Real content here.</p>
      </body>
    </html>
    """
    _patch_client(monkeypatch, FakeClient(FakeResponse(html)))

    content = await scrape_url("https://example.com")

    assert "Real content here." in content
    assert "Navigation menu" not in content
    assert "alert" not in content
    assert ".hidden" not in content
    assert "Footer text" not in content


@pytest.mark.asyncio
async def test_scrape_url_works_without_title_tag(monkeypatch):
    html = "<html><body><p>No title here.</p></body></html>"
    _patch_client(monkeypatch, FakeClient(FakeResponse(html)))

    content = await scrape_url("https://example.com")

    assert "No title here." in content
    # Should not crash or include "Title: None"
    assert "Title: None" not in content


@pytest.mark.asyncio
async def test_scrape_url_returns_string(monkeypatch):
    html = "<html><body><p>Hello</p></body></html>"
    _patch_client(monkeypatch, FakeClient(FakeResponse(html)))

    result = await scrape_url("https://example.com")

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests — content truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_url_truncates_content_at_50000_chars(monkeypatch):
    # Build a large page — text content well over the 50k limit
    long_text = "word " * 15000  # 75,000 chars
    html = f"<html><body><p>{long_text}</p></body></html>"
    _patch_client(monkeypatch, FakeClient(FakeResponse(html)))

    content = await scrape_url("https://example.com")

    assert len(content) <= 50000


@pytest.mark.asyncio
async def test_scrape_url_does_not_truncate_content_under_50000(monkeypatch):
    text = "word " * 1000  # 5,000 chars — well under limit
    html = f"<html><head><title>Short</title></head><body><p>{text}</p></body></html>"
    _patch_client(monkeypatch, FakeClient(FakeResponse(html)))

    content = await scrape_url("https://example.com")

    # Full text should be present (not truncated)
    assert "word" in content
    assert len(content) < 50000


# ---------------------------------------------------------------------------
# Tests — HTTP error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_url_raises_scrape_error_on_404(monkeypatch):
    _patch_client(monkeypatch, FakeClient(FakeResponse("<html/>", status_code=404)))

    with pytest.raises(ScrapeError) as exc_info:
        await scrape_url("https://example.com/missing")

    assert "404" in str(exc_info.value)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_scrape_url_raises_scrape_error_on_500(monkeypatch):
    _patch_client(monkeypatch, FakeClient(FakeResponse("<html/>", status_code=500)))

    with pytest.raises(ScrapeError) as exc_info:
        await scrape_url("https://example.com")

    assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_scrape_url_raises_scrape_error_on_timeout(monkeypatch):
    client = FakeClient(raise_on_get=httpx.TimeoutException("timed out"))
    _patch_client(monkeypatch, client)

    with pytest.raises(ScrapeError) as exc_info:
        await scrape_url("https://example.com")

    assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_scrape_url_raises_scrape_error_on_connection_error(monkeypatch):
    client = FakeClient(raise_on_get=httpx.ConnectError("connection refused"))
    _patch_client(monkeypatch, client)

    with pytest.raises(ScrapeError) as exc_info:
        await scrape_url("https://unreachable.example.com")

    assert isinstance(exc_info.value, ScrapeError)


# ---------------------------------------------------------------------------
# Tests — ScrapeError attributes
# ---------------------------------------------------------------------------


def test_scrape_error_carries_status_code():
    err = ScrapeError("not found", status_code=404)
    assert err.status_code == 404
    assert err.message == "not found"


def test_scrape_error_status_code_is_optional():
    err = ScrapeError("network error")
    assert err.status_code is None
    assert "network error" in str(err)
