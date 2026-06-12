"""Tests for the project-events recorder: non-fatal + sanitized."""

import pytest

from app.services import project_events as pe
from app.services.project_events import _sanitize_metadata, record_project_event


def test_sanitize_metadata_keeps_scalars_and_scalar_lists():
    out = _sanitize_metadata(
        {
            "records": 3,
            "label": "good",
            "ok": True,
            "ratio": 0.5,
            "none": None,
            "tags": ["a", "b", {"x": 1}],  # nested object filtered out of list
            "obj": {"nested": 1},  # whole non-scalar value dropped
        }
    )
    assert out["records"] == 3
    assert out["label"] == "good"
    assert out["ok"] is True
    assert out["ratio"] == 0.5
    assert out["none"] is None
    assert out["tags"] == ["a", "b"]
    assert "obj" not in out


def test_sanitize_metadata_non_dict_returns_empty():
    assert _sanitize_metadata(None) == {}
    assert _sanitize_metadata("not-a-dict") == {}
    assert _sanitize_metadata(42) == {}


@pytest.mark.asyncio
async def test_record_project_event_never_raises_on_db_failure(monkeypatch):
    """A failing DB write must be swallowed — logging cannot break the pipeline."""

    class BoomSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def add(self, _obj):
            pass

        async def commit(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(pe, "async_session_factory", lambda: BoomSession())

    # Must not raise.
    await record_project_event(1, 1, "extraction.failed", level="error", message="x")
