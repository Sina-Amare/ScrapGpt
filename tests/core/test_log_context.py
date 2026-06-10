"""Unit tests for app/core/log_context.py."""

import pytest

from app.core.log_context import (
    bind_user_id,
    clear_context,
    get_log_context,
    set_page_context,
    set_request_context,
    set_task_context,
)


@pytest.fixture(autouse=True)
def _clean_context():
    """Ensure context is clean before and after each test."""
    clear_context()
    yield
    clear_context()


class TestGetLogContext:
    def test_empty_context_returns_empty_dict(self):
        assert get_log_context() == {}

    def test_set_request_id_appears_in_context(self):
        set_request_context(request_id="req-123")
        ctx = get_log_context()
        assert ctx["request_id"] == "req-123"
        assert "user_id" not in ctx

    def test_set_request_id_with_user_id(self):
        set_request_context(request_id="req-456", user_id=7)
        ctx = get_log_context()
        assert ctx["request_id"] == "req-456"
        assert ctx["user_id"] == 7

    def test_set_task_context(self):
        set_task_context(project_id=42, user_id=3)
        ctx = get_log_context()
        assert ctx["project_id"] == 42
        assert ctx["user_id"] == 3

    def test_set_page_context(self):
        set_page_context(page_id=101)
        ctx = get_log_context()
        assert ctx["page_id"] == 101

    def test_bind_user_id(self):
        bind_user_id(user_id=99)
        ctx = get_log_context()
        assert ctx["user_id"] == 99

    def test_combined_context(self):
        set_request_context(request_id="r1", user_id=1)
        set_task_context(project_id=5, user_id=2)
        set_page_context(page_id=10)
        ctx = get_log_context()
        assert ctx["request_id"] == "r1"
        assert ctx["user_id"] == 2  # task overrides request
        assert ctx["project_id"] == 5
        assert ctx["page_id"] == 10

    def test_clear_context_resets_all(self):
        set_request_context(request_id="r1", user_id=1)
        set_task_context(project_id=5, user_id=2)
        set_page_context(page_id=10)
        clear_context()
        assert get_log_context() == {}

    def test_none_values_omitted(self):
        """Keys with None values should not appear in the context dict."""
        clear_context()
        # After clear, all are None — dict should be empty
        assert get_log_context() == {}