"""HTTP fetcher: static httpx with optional Playwright browser fallback."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from app.core.config import settings
from app.services.url_validator import (
    URLValidationError,
    validate_redirect_target,
    validate_url,
)

logger = logging.getLogger(__name__)

_CONTENT_TYPE_ALLOWLIST = ("text/html", "text/plain", "application/xhtml+xml")


def _format_browser_exception(exc: Exception) -> str:
    detail = str(exc).strip()
    if detail:
        return f"Browser fetch failed: {detail}"
    return f"Browser fetch failed: {exc.__class__.__name__}"


class FetchError(Exception):
    def __init__(self, message: str, error_code: str = "FETCH_FAILED") -> None:
        super().__init__(message)
        self.error_code = error_code


class RenderModeUsed(str, Enum):
    STATIC = "STATIC"
    BROWSER = "BROWSER"


@dataclass
class FetchResult:
    html: str
    content_hash: str
    final_url: str
    render_mode_used: RenderModeUsed
    status_code: int
    elapsed_ms: int
    fetch_metadata: dict = field(default_factory=dict)


def _browser_result_from_html(
    *,
    html_raw: bytes,
    final_url: str,
    status: int,
    elapsed_ms: int,
) -> FetchResult:
    original_bytes = len(html_raw)
    truncated = original_bytes > settings.MAX_FETCH_BYTES
    if truncated:
        html_raw = html_raw[: settings.MAX_FETCH_BYTES]
    analyzed_bytes = len(html_raw)
    html = html_raw.decode("utf-8", errors="replace")
    content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

    return FetchResult(
        html=html,
        content_hash=content_hash,
        final_url=final_url,
        render_mode_used=RenderModeUsed.BROWSER,
        status_code=status,
        elapsed_ms=elapsed_ms,
        fetch_metadata={
            "original_bytes": original_bytes,
            "analyzed_bytes": analyzed_bytes,
            "truncated": truncated,
            "elapsed_ms": elapsed_ms,
        },
    )


async def _static_fetch(url: str) -> FetchResult:
    """Fetch a URL with httpx, manually validating each redirect.

    One AsyncClient is created for the full redirect chain to reuse the
    underlying connection pool and avoid a new TLS handshake per hop.
    """
    current_url = url
    hops = 0
    t0 = time.monotonic()

    async with httpx.AsyncClient(
        timeout=settings.SCRAPE_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": settings.USER_AGENT},
    ) as client:
        while True:
            try:
                resp = await client.get(current_url)
            except httpx.TimeoutException as exc:
                raise FetchError(
                    f"Request timed out for {current_url}", "FETCH_TIMEOUT"
                ) from exc
            except httpx.RequestError as exc:
                raise FetchError(f"Network error: {exc}", "FETCH_FAILED") from exc

            if resp.is_redirect:
                if hops >= settings.MAX_REDIRECTS:
                    raise FetchError(
                        f"Too many redirects (>{settings.MAX_REDIRECTS})",
                        "TOO_MANY_REDIRECTS",
                    )
                location = resp.headers.get("location", "")
                if not location:
                    raise FetchError("Redirect with no Location header", "FETCH_FAILED")
                try:
                    current_url = validate_redirect_target(location, current_url)
                except URLValidationError as exc:
                    raise FetchError(
                        f"Redirect target blocked: {exc}", "URL_BLOCKED"
                    ) from exc
                hops += 1
                continue

            # Final response
            status = resp.status_code

            ct = resp.headers.get("content-type", "")
            if not any(allowed in ct for allowed in _CONTENT_TYPE_ALLOWLIST):
                raise FetchError(
                    f"Unsupported content-type: {ct}", "UNSUPPORTED_CONTENT_TYPE"
                )

            try:
                body = await resp.aread()
            except Exception as exc:
                raise FetchError(f"Failed to read response body: {exc}") from exc

            original_bytes = len(body)
            truncated = original_bytes > settings.MAX_FETCH_BYTES
            if truncated:
                body = body[: settings.MAX_FETCH_BYTES]
            analyzed_bytes = len(body)

            html = body.decode("utf-8", errors="replace")
            content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
            elapsed = int((time.monotonic() - t0) * 1000)

            return FetchResult(
                html=html,
                content_hash=content_hash,
                final_url=current_url,
                render_mode_used=RenderModeUsed.STATIC,
                status_code=status,
                elapsed_ms=elapsed,
                fetch_metadata={
                    "hops": hops,
                    "content_type": ct,
                    "original_bytes": original_bytes,
                    "analyzed_bytes": analyzed_bytes,
                    "truncated": truncated,
                    "elapsed_ms": elapsed,
                },
            )


def _should_use_threaded_browser_fetch() -> bool:
    if sys.platform != "win32":
        return False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    return "Selector" in loop.__class__.__name__


def _ensure_windows_proactor_policy_for_playwright() -> None:
    if sys.platform != "win32":
        return
    policy_factory = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if policy_factory is None:
        return
    if "Proactor" not in asyncio.get_event_loop_policy().__class__.__name__:
        asyncio.set_event_loop_policy(policy_factory())


def _browser_fetch_sync(url: str) -> FetchResult:
    """Fetch with Playwright sync API for Windows selector event loops."""
    _ensure_windows_proactor_policy_for_playwright()
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError as exc:
        raise FetchError(
            "Browser rendering requires Playwright. "
            "Install it: venv\\Scripts\\python.exe -m playwright install chromium",
            "BROWSER_UNAVAILABLE",
        ) from exc

    t0 = time.monotonic()
    blocked: list[FetchError] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=settings.USER_AGENT,
                    java_script_enabled=True,
                )
                try:
                    def _route_handler(route: Any) -> None:
                        req_url = route.request.url
                        if not req_url.startswith(("http://", "https://")):
                            route.continue_()
                            return
                        try:
                            validate_url(req_url)
                            route.continue_()
                        except URLValidationError as exc:
                            if not blocked:
                                blocked.append(
                                    FetchError(
                                        f"Browser blocked URL: {exc}",
                                        "BROWSER_URL_BLOCKED",
                                    )
                                )
                            route.abort("blockedbyclient")

                    context.route("**", _route_handler)

                    page = context.new_page()
                    response = page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=settings.SCRAPE_TIMEOUT * 1000,
                    )

                    if blocked:
                        raise blocked[0]

                    if response is None:
                        raise FetchError("Browser got no response", "FETCH_FAILED")

                    final_url = page.url
                    try:
                        validate_url(final_url)
                    except URLValidationError as exc:
                        raise FetchError(
                            f"Final URL blocked: {exc}", "BROWSER_URL_BLOCKED"
                        ) from exc

                    html_raw = page.content().encode("utf-8")
                    elapsed = int((time.monotonic() - t0) * 1000)
                    return _browser_result_from_html(
                        html_raw=html_raw,
                        final_url=final_url,
                        status=response.status,
                        elapsed_ms=elapsed,
                    )
                finally:
                    context.close()
            finally:
                browser.close()
    except FetchError:
        raise
    except Exception as exc:
        if blocked:
            raise blocked[0]
        raise FetchError(_format_browser_exception(exc), "FETCH_FAILED") from exc


async def _browser_fetch_async(url: str) -> FetchResult:
    """Fetch a URL with Playwright Chromium. Raises FetchError if unavailable."""
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415
    except ImportError as exc:
        raise FetchError(
            "Browser rendering requires Playwright. "
            "Install it: venv\\Scripts\\python.exe -m playwright install chromium",
            "BROWSER_UNAVAILABLE",
        ) from exc

    t0 = time.monotonic()
    # Initialized before try so the except handler can check it even if
    # page.goto() throws before the `if blocked:` guard inside the try runs.
    blocked: list[FetchError] = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=settings.USER_AGENT,
                    java_script_enabled=True,
                )
                try:
                    # SSRF prevention: intercept every outgoing request and block
                    # private / metadata IPs before the connection is established.
                    #
                    # DNS rebinding limitation: validate_url resolves DNS here (in
                    # Python), but the browser re-resolves at the TCP connect step.
                    # An attacker-controlled domain can return a public IP during
                    # this check and switch to a private IP for the actual connect.
                    # That race is not preventable at the application layer. Full
                    # mitigation requires an egress firewall or IP-pinned transport.

                    async def _route_handler(route: Any) -> None:
                        req_url = route.request.url
                        # Only validate http/https; let data:/blob: through
                        if not req_url.startswith(("http://", "https://")):
                            await route.continue_()
                            return
                        try:
                            validate_url(req_url)
                            await route.continue_()
                        except URLValidationError as exc:
                            if not blocked:
                                blocked.append(
                                    FetchError(
                                        f"Browser blocked URL: {exc}",
                                        "BROWSER_URL_BLOCKED",
                                    )
                                )
                            await route.abort("blockedbyclient")

                    await context.route("**", _route_handler)

                    page = await context.new_page()
                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=settings.SCRAPE_TIMEOUT * 1000,
                    )

                    if blocked:
                        raise blocked[0]

                    if response is None:
                        raise FetchError("Browser got no response", "FETCH_FAILED")

                    status = response.status
                    final_url = page.url

                    # Belt-and-suspenders: validate final URL in case JS navigation
                    # landed on a redirected destination outside the route handler.
                    try:
                        validate_url(final_url)
                    except URLValidationError as exc:
                        raise FetchError(
                            f"Final URL blocked: {exc}", "BROWSER_URL_BLOCKED"
                        ) from exc

                    html_raw = (await page.content()).encode("utf-8")
                finally:
                    await context.close()
            finally:
                await browser.close()
    except FetchError:
        raise
    except Exception as exc:
        # Real Playwright throws from page.goto() when a route handler calls
        # route.abort(). Check blocked first so the error code is correct.
        if blocked:
            raise blocked[0]
        raise FetchError(_format_browser_exception(exc), "FETCH_FAILED") from exc

    elapsed = int((time.monotonic() - t0) * 1000)
    return _browser_result_from_html(
        html_raw=html_raw,
        final_url=final_url,
        status=status,
        elapsed_ms=elapsed,
    )


async def _browser_fetch(url: str) -> FetchResult:
    if _should_use_threaded_browser_fetch():
        return await asyncio.to_thread(_browser_fetch_sync, url)
    return await _browser_fetch_async(url)


def _is_sparse(html: str) -> bool:
    """Heuristic: page is too sparse to extract from without JS rendering."""
    stripped = html.replace(" ", "").replace("\n", "")
    return len(stripped) < 500


async def fetch_url(url: str, render_mode: str = "AUTO") -> FetchResult:
    """
    Fetch a URL according to render_mode.

    AUTO: try static first; if content is sparse, attempt browser (no crash if unavailable).
    STATIC: static only.
    BROWSER: browser only; raises FetchError with BROWSER_UNAVAILABLE if not installed.
    """
    if render_mode == "BROWSER":
        return await _browser_fetch(url)

    result = await _static_fetch(url)

    if render_mode == "AUTO" and _is_sparse(result.html):
        logger.info("fetcher.sparse_content_browser_fallback", extra={"url": url})
        try:
            result = await _browser_fetch(url)
        except FetchError as exc:
            if exc.error_code == "BROWSER_UNAVAILABLE":
                logger.info(
                    "fetcher.browser_unavailable_fallback_static",
                    extra={"url": url},
                )
                result.fetch_metadata["browser_fallback_skipped"] = True
            else:
                raise

    return result
