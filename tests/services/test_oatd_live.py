"""Opt-in live E2E tests for bot-detection bypass.

Run with:
    RUN_OATD_LIVE=1 venv\\Scripts\\python.exe -m pytest \
        tests/services/test_oatd_live.py -q -s

What OATD uses (confirmed by inspection):
  - Cloudflare JS challenge + Turnstile as fallback when headless is detected
  - Static fetch:  403 with binary/compressed block page
  - Headless browsers (even camoufox): get the CF challenge page with Turnstile

What each tier achieves on OATD:
  - STATIC         -> 403 blocked (bot-detected immediately)
  - camoufox       -> reaches the CF challenge page but CF serves Turnstile
                      (headless Firefox still detected by CF's advanced check)
  - FlareSolverr   -> PASSES (uses a real non-headless Chrome, can solve Turnstile)
  - User cookies   -> PASSES (cf_clearance cookie bypasses challenge entirely)

Tests are parameterised to fail when the expected tier is not configured,
and skip when the tier is not available, so the output always tells you
exactly what worked and what you need to do to unblock it.

Set env vars to enable optional tiers:
  RUN_OATD_LIVE=1             required for all tests
  FLARESOLVERR_URL=http://...  enables FlareSolverr tier test
"""

from __future__ import annotations

import os

import pytest

from app.core.config import settings
from app.services.anti_bot import CHALLENGE_MESSAGES, anti_bot_challenge_reason
from app.services.fetcher import RenderModeUsed
from app.services.fetcher import fetch_url

OATD_URL = (
    "https://www.oatd.org/oatd/search?"
    "q=statistics&form=basic&last2yr=y&level.facet=doctoral&start=241"
)

_LIVE = pytest.mark.skipif(
    os.environ.get("RUN_OATD_LIVE") != "1",
    reason="Opt-in live test — requires RUN_OATD_LIVE=1",
)
_MIN_REAL_BYTES = 2_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report(label: str, result) -> None:
    reason = anti_bot_challenge_reason(result.html, result.final_url)
    print(
        f"\n[{label}] render_mode={result.render_mode_used}  "
        f"status={result.status_code}  bytes={len(result.html)}  "
        f"challenge={reason or 'none'}"
    )


def _assert_real_content(result, *, mode: str) -> None:
    reason = anti_bot_challenge_reason(result.html, result.final_url)
    if reason:
        pytest.fail(
            f"[{mode}] Still blocked.\n"
            f"  render_mode: {result.render_mode_used}\n"
            f"  challenge:   {reason}\n"
            f"  hint:        {CHALLENGE_MESSAGES.get(reason, '')}"
        )
    assert len(result.html) >= _MIN_REAL_BYTES, (
        f"[{mode}] No challenge but only {len(result.html)} bytes — likely empty page"
    )
    html_lower = result.html.lower()
    keywords = ("oatd", "dissertation", "thesis", "doctoral", "statistics")
    assert any(kw in html_lower for kw in keywords), (
        "Page loaded but missing OATD content keywords. "
        f"First 300 chars: {result.html[:300]}"
    )


# ---------------------------------------------------------------------------
# Tier 1: Static fetch — expected to be blocked on OATD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@_LIVE
async def test_static_is_blocked_by_oatd():
    """Static fetch should be blocked (403) — this is the baseline we need to beat."""
    from app.services.fetcher import _static_fetch
    result = await _static_fetch(OATD_URL)
    _report("STATIC", result)

    # 403 or a CF challenge = blocked, which is expected for static on OATD
    reason = anti_bot_challenge_reason(result.html, result.final_url)
    is_blocked = (
        result.status_code in (401, 403, 429, 503) or reason is not None
    )
    assert is_blocked, (
        f"Static unexpectedly passed OATD (status={result.status_code})"
        " — CF may have relaxed its rules this run, which is fine."
    )
    print(f"  Confirmed: static is blocked (expected). Challenge: {reason or 'binary block page'}")


# ---------------------------------------------------------------------------
# Tier 2: camoufox — reaches CF challenge but Turnstile blocks it on OATD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@_LIVE
async def test_camoufox_reaches_challenge_but_needs_flaresolverr():
    """camoufox should reach the CF challenge page (better than static 403).

    OATD's CF serves Turnstile when headless is detected.  camoufox can't solve
    Turnstile headlessly — FlareSolverr is needed.
    This test PASSES if camoufox at least got further than a raw block.
    """
    from app.services.fetcher import _camoufox_fetch
    try:
        result = await _camoufox_fetch(OATD_URL)
    except Exception as exc:
        pytest.skip(f"camoufox unavailable: {exc}")  # type: ignore[assignment]

    _report("CAMOUFOX", result)

    reason = anti_bot_challenge_reason(result.html, result.final_url)
    if not reason:
        # camoufox actually passed! Great.
        _assert_real_content(result, mode="CAMOUFOX")
        print("  BONUS: camoufox passed CF this run!")
        return

    # We got the challenge page — that's better than a raw binary block.
    # Confirm we at least got HTML from CF (not a raw TCP block).
    assert result.status_code in (200, 403, 503), (
        f"Unexpected status {result.status_code}"
    )
    assert len(result.html) > 1000, (
        "Expected at least a challenge page, got almost nothing"
    )
    print(
        f"  camoufox reached CF challenge ({reason}), "
        "needs FlareSolverr to solve Turnstile"
    )


# ---------------------------------------------------------------------------
# Tier 3: FlareSolverr — the correct solution for OATD's Turnstile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@_LIVE
async def test_flaresolverr_bypasses_cloudflare():
    """FlareSolverr (non-headless Chrome) MUST bypass OATD's Cloudflare Turnstile.

    Skipped if FLARESOLVERR_URL is not set in .env.
    To run:
      1. docker run -d -p 8191:8191 flaresolverr/flaresolverr:latest
      2. Set FLARESOLVERR_URL=http://localhost:8191 in .env
      3. Re-run this test
    """
    if not settings.FLARESOLVERR_URL:
        pytest.skip(
            "FLARESOLVERR_URL not set. "
            "Run: docker run -d -p 8191:8191 flaresolverr/flaresolverr:latest "
            "then add FLARESOLVERR_URL=http://localhost:8191 to .env"
        )

    from app.services.fetcher import _flaresolverr_fetch
    result = await _flaresolverr_fetch(OATD_URL)
    _report("FLARESOLVERR", result)
    _assert_real_content(result, mode="FLARESOLVERR")
    print(f"  PASS: FlareSolverr bypassed CF Turnstile on OATD!")


# ---------------------------------------------------------------------------
# Full cascade: AUTO mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@_LIVE
async def test_auto_cascade_uses_stealth_backend():
    """AUTO mode must trigger the stealth cascade (not fall back to static result).

    Whether the cascade ultimately succeeds depends on what's configured:
    - Without FlareSolverr: camoufox is tried but Turnstile blocks it on OATD
    - With FlareSolverr:    succeeds
    """
    result = await fetch_url(OATD_URL, "AUTO")
    _report("AUTO", result)

    # The cascade MUST have been triggered (not returned static 403)
    assert result.render_mode_used != RenderModeUsed.STATIC, (
        "AUTO mode returned the static 403 result without trying stealth — "
        "the 4xx trigger is not working."
    )

    reason = anti_bot_challenge_reason(result.html, result.final_url)
    if not reason:
        _assert_real_content(result, mode="AUTO")
        print(f"  PASS: bypassed via {result.render_mode_used}")
    elif settings.FLARESOLVERR_URL:
        pytest.fail(
            f"FlareSolverr is configured but AUTO still blocked by {reason}. "
            "Check that FlareSolverr is running and reachable."
        )
    else:
        print(
            f"  Cascade ran via {result.render_mode_used} but CF Turnstile blocked it. "
            "Set FLARESOLVERR_URL to complete the bypass."
        )
        # This is expected — not a failure of the cascade logic, just Turnstile
