"""Context variables for structured log correlation.

Provides request-scoped and task-scoped context that is automatically
injected into every log record by the ContextInjectingFilter in
logging_config.py.  This allows log lines from background tasks and
async handlers to carry project_id, user_id, request_id, and page_id
without every call site passing them as extra={} arguments.

Usage:
    # HTTP request middleware (main.py)
    set_request_context(request_id=uuid_str, user_id=user.id)

    # Background extraction task
    set_task_context(project_id=42, user_id=7)

    # Page loop inside extraction
    set_page_context(page_id=101)
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
_project_id: ContextVar[Optional[int]] = ContextVar("project_id", default=None)
_page_id: ContextVar[Optional[int]] = ContextVar("page_id", default=None)


def set_request_context(
    request_id: str, user_id: Optional[int] = None
) -> None:
    """Bind HTTP request-scoped context variables."""
    _request_id.set(request_id)
    if user_id is not None:
        _user_id.set(user_id)


def set_task_context(project_id: int, user_id: int) -> None:
    """Bind background task-scoped context variables."""
    _project_id.set(project_id)
    _user_id.set(user_id)


def bind_user_id(user_id: int) -> None:
    """Bind user_id to the current log context.

    Called from get_current_user / get_optional_user after
    successful JWT decode, so that all subsequent log lines
    in the request carry the authenticated user's ID.
    """
    _user_id.set(user_id)


def set_page_context(page_id: int) -> None:
    """Bind per-page context inside the extraction page loop."""
    _page_id.set(page_id)


def clear_context() -> None:
    """Reset all context variables (call at end of request/task)."""
    _request_id.set(None)
    _user_id.set(None)
    _project_id.set(None)
    _page_id.set(None)


def get_log_context() -> dict:
    """Return a dict of all currently-set context variables.

    Keys with None values are omitted so they don't appear as
    empty fields in JSON output.
    """
    ctx: dict = {}
    v = _request_id.get()
    if v is not None:
        ctx["request_id"] = v
    v = _user_id.get()
    if v is not None:
        ctx["user_id"] = v
    v = _project_id.get()
    if v is not None:
        ctx["project_id"] = v
    v = _page_id.get()
    if v is not None:
        ctx["page_id"] = v
    return ctx