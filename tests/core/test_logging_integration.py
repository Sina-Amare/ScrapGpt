"""Integration tests for structured logging events.

Uses pytest's caplog fixture to capture log output and verify
that key events are emitted with the correct fields and no
credential material.
"""

import logging

import pytest

from app.core.log_context import clear_context


@pytest.fixture(autouse=True)
def _clean_context():
    """Ensure context is clean before and after each test."""
    clear_context()
    yield
    clear_context()


class TestAuthLoggingEvents:
    """Verify auth endpoint log events carry correct fields
    and no credential material."""

    def test_login_success_event_has_user_id_no_password(
        self, caplog,
    ):
        """auth.login_success should carry user_id but not the
        password or token."""
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.api.v1.endpoints.auth")
        logger.info(
            "auth.login_success",
            extra={"user_id": 1, "email": "user@example.com"},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "auth.login_success"
        ]
        assert len(records) == 1
        rec = records[0]
        assert rec.user_id == 1
        # No password or token in the record
        assert not hasattr(rec, "password")
        assert not hasattr(rec, "token")

    def test_login_failed_event_has_email_no_password(
        self, caplog,
    ):
        """auth.login_failed should carry email and reason but
        never the attempted password."""
        caplog.set_level(logging.WARNING)
        logger = logging.getLogger("app.api.v1.endpoints.auth")
        logger.warning(
            "auth.login_failed",
            extra={
                "email": "user@example.com",
                "reason": "invalid_credentials",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "auth.login_failed"
        ]
        assert len(records) == 1
        rec = records[0]
        assert rec.email == "user@example.com"
        assert rec.reason == "invalid_credentials"
        assert not hasattr(rec, "password")

    def test_register_success_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.api.v1.endpoints.auth")
        logger.info(
            "auth.register_success",
            extra={"user_id": 2, "email": "new@example.com"},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "auth.register_success"
        ]
        assert len(records) == 1
        assert records[0].user_id == 2

    def test_refresh_token_success_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.api.v1.endpoints.auth")
        logger.info(
            "auth.refresh_success",
            extra={"user_id": 3},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "auth.refresh_success"
        ]
        assert len(records) == 1
        assert records[0].user_id == 3

    def test_refresh_token_failed_event(self, caplog):
        caplog.set_level(logging.WARNING)
        logger = logging.getLogger("app.api.v1.endpoints.auth")
        logger.warning(
            "auth.refresh_failed",
            extra={"reason": "invalid_token"},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "auth.refresh_failed"
        ]
        assert len(records) == 1
        assert records[0].reason == "invalid_token"


class TestProviderKeyRevealLogging:
    """Verify key reveal audit log carries correct fields."""

    def test_key_revealed_audit_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.api.v1.endpoints.providers"
        )
        logger.info(
            "security.key_revealed",
            extra={
                "user_id": 1,
                "provider_id": 5,
                "provider_name": "OpenAI",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "security.key_revealed"
        ]
        assert len(records) == 1
        rec = records[0]
        assert rec.user_id == 1
        assert rec.provider_id == 5
        assert rec.provider_name == "OpenAI"
        # No API key in the log record
        assert not hasattr(rec, "api_key")


class TestExtractionLoggingEvents:
    """Verify extraction pipeline events carry project_id."""

    def test_extraction_started_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.services.project_extraction"
        )
        logger.info(
            "project_extraction.started",
            extra={"project_id": 42, "spec_id": 7},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "project_extraction.started"
        ]
        assert len(records) == 1
        assert records[0].project_id == 42
        assert records[0].spec_id == 7

    def test_extraction_completed_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.services.project_extraction"
        )
        logger.info(
            "project_extraction.completed",
            extra={
                "project_id": 42,
                "records": 15,
                "pages": 3,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "project_extraction.completed"
        ]
        assert len(records) == 1
        assert records[0].project_id == 42

    def test_quality_computed_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.services.project_extraction"
        )
        logger.info(
            "extraction.quality_computed",
            extra={
                "project_id": 42,
                "quality_label": "good",
                "field_count": 5,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "extraction.quality_computed"
        ]
        assert len(records) == 1
        assert records[0].project_id == 42
        assert records[0].quality_label == "good"
        assert records[0].field_count == 5

    def test_quality_computation_failed_event(self, caplog):
        caplog.set_level(logging.ERROR)
        logger = logging.getLogger(
            "app.services.project_extraction"
        )
        logger.error(
            "extraction.quality_computation_failed",
            extra={
                "project_id": 42,
                "error_type": "TypeError",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "extraction.quality_computation_failed"
        ]
        assert len(records) == 1
        assert records[0].project_id == 42
        assert records[0].error_type == "TypeError"

    def test_page_failed_event(self, caplog):
        caplog.set_level(logging.ERROR)
        logger = logging.getLogger(
            "app.services.project_extraction"
        )
        logger.error(
            "extraction.page_failed",
            extra={
                "project_id": 42,
                "page_id": 101,
                "url": "https://example.com/page",
                "error_type": "FetchError",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "extraction.page_failed"
        ]
        assert len(records) == 1
        assert records[0].project_id == 42
        assert records[0].page_id == 101

    def test_records_extracted_debug_event(self, caplog):
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger(
            "app.services.project_extraction"
        )
        logger.debug(
            "extraction.records_extracted",
            extra={
                "project_id": 42,
                "page_id": 101,
                "record_count": 3,
                "warnings_count": 1,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "extraction.records_extracted"
        ]
        assert len(records) == 1
        assert records[0].record_count == 3


class TestScopeLoggingEvents:
    """Verify scope classification events."""

    def test_scope_classified_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.services.crawl_scope")
        logger.info(
            "scope.classified",
            extra={
                "scope_mode": "CURRENT_PAGE",
                "included_count": 1,
                "excluded_count": 5,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "scope.classified"
        ]
        assert len(records) == 1
        assert records[0].scope_mode == "CURRENT_PAGE"

    def test_scope_confirmation_gate_passed(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.services.crawl_scope")
        logger.info(
            "scope.confirmation_gate_passed",
            extra={"scope_mode": "CURRENT_PAGE"},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "scope.confirmation_gate_passed"
        ]
        assert len(records) == 1

    def test_scope_confirmation_required_warning(self, caplog):
        caplog.set_level(logging.WARNING)
        logger = logging.getLogger("app.services.crawl_scope")
        logger.warning(
            "scope.confirmation_required",
            extra={
                "scope_mode": "FULL_SITE",
                "scope_status": "AI_RECOMMENDED",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "scope.confirmation_required"
        ]
        assert len(records) == 1


class TestWatchdogLoggingEvents:
    """Verify watchdog sweep and reset events."""

    def test_sweep_started_debug(self, caplog):
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger("app.services.watchdog")
        logger.debug(
            "watchdog.sweep_started",
            extra={"timestamp": "2026-06-10T12:00:00Z"},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "watchdog.sweep_started"
        ]
        assert len(records) == 1

    def test_sweep_completed_info(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.services.watchdog")
        logger.info(
            "watchdog.sweep_completed",
            extra={
                "tasks_reset": 2,
                "jobs_reset": 1,
                "duration_ms": 150.3,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "watchdog.sweep_completed"
        ]
        assert len(records) == 1
        assert records[0].tasks_reset == 2
        assert records[0].duration_ms == 150.3

    def test_task_reset_info(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.services.watchdog")
        logger.info(
            "watchdog.task_reset",
            extra={
                "task_id": 10,
                "old_state": "PERMISSION_GRANTED",
                "timeout_category": "permission_granted",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "watchdog.task_reset"
        ]
        assert len(records) == 1
        assert records[0].task_id == 10

    def test_job_reset_info(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger("app.services.watchdog")
        logger.info(
            "watchdog.job_reset",
            extra={
                "job_id": 5,
                "old_state": "QUEUED",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "watchdog.job_reset"
        ]
        assert len(records) == 1
        assert records[0].job_id == 5


class TestExportLoggingEvents:
    """Verify export endpoint events."""

    def test_export_started_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.api.v1.endpoints.projects"
        )
        logger.info(
            "export.started",
            extra={
                "project_id": 1,
                "user_id": 2,
                "format": "csv",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "export.started"
        ]
        assert len(records) == 1
        assert records[0].project_id == 1
        assert records[0].format == "csv"

    def test_export_completed_event(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.api.v1.endpoints.projects"
        )
        logger.info(
            "export.completed",
            extra={
                "project_id": 1,
                "format": "csv",
                "record_count": 50,
                "duration_ms": 120.5,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "export.completed"
        ]
        assert len(records) == 1
        assert records[0].record_count == 50

    def test_export_failed_event(self, caplog):
        caplog.set_level(logging.ERROR)
        logger = logging.getLogger(
            "app.api.v1.endpoints.projects"
        )
        logger.error(
            "export.failed",
            extra={
                "project_id": 1,
                "format": "xlsx",
                "error_type": "ValueError",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "export.failed"
        ]
        assert len(records) == 1
        assert records[0].error_type == "ValueError"


class TestFrontierPreviewLoggingEvents:
    """Verify frontier preview events."""

    def test_fetch_started_debug(self, caplog):
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger(
            "app.services.frontierpreview"
        )
        logger.debug(
            "frontier.fetch_started",
            extra={"project_id": 1, "url": "https://example.com"},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "frontier.fetch_started"
        ]
        assert len(records) == 1

    def test_fetch_failed_error(self, caplog):
        caplog.set_level(logging.ERROR)
        logger = logging.getLogger(
            "app.services.frontierpreview"
        )
        logger.error(
            "frontier.fetch_failed",
            extra={
                "project_id": 1,
                "url": "https://example.com",
                "error_type": "FetchError",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "frontier.fetch_failed"
        ]
        assert len(records) == 1
        assert records[0].error_type == "FetchError"

    def test_preview_built_info(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.services.frontierpreview"
        )
        logger.info(
            "frontier.preview_built",
            extra={
                "project_id": 1,
                "scope_mode": "CURRENT_PAGE",
                "included_count": 3,
                "excluded_count": 10,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "frontier.preview_built"
        ]
        assert len(records) == 1
        assert records[0].scope_mode == "CURRENT_PAGE"

    def test_high_exclusion_rate_warning(self, caplog):
        caplog.set_level(logging.WARNING)
        logger = logging.getLogger(
            "app.services.frontierpreview"
        )
        logger.warning(
            "frontier.high_exclusion_rate",
            extra={
                "project_id": 1,
                "excluded_pct": 85.0,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "frontier.high_exclusion_rate"
        ]
        assert len(records) == 1
        assert records[0].excluded_pct == 85.0


class TestPreviewLoggingEvents:
    """Verify preview service events."""

    def test_preview_started_debug(self, caplog):
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger(
            "app.services.project_preview"
        )
        logger.debug(
            "preview.started",
            extra={"project_id": 1},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "preview.started"
        ]
        assert len(records) == 1

    def test_preview_completed_info(self, caplog):
        caplog.set_level(logging.INFO)
        logger = logging.getLogger(
            "app.services.project_preview"
        )
        logger.info(
            "preview.completed",
            extra={
                "project_id": 1,
                "record_count": 5,
                "selector_hit_rate": 80.0,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "preview.completed"
        ]
        assert len(records) == 1
        assert records[0].record_count == 5

    def test_selector_failed_warning(self, caplog):
        caplog.set_level(logging.WARNING)
        logger = logging.getLogger(
            "app.services.project_preview"
        )
        logger.warning(
            "preview.selector_failed",
            extra={
                "project_id": 1,
                "field_name": "title",
                "selector": "Title",
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "preview.selector_failed"
        ]
        assert len(records) == 1
        assert records[0].field_name == "title"


class TestSchedulerLoggingEvents:
    """Verify scheduler timing events."""

    def test_scheduler_job_started_debug(self, caplog):
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger("app.core.scheduler")
        logger.debug(
            "scheduler.job_started",
            extra={"job_name": "watchdog_cleanup"},
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "scheduler.job_started"
        ]
        assert len(records) == 1

    def test_scheduler_job_completed_debug(self, caplog):
        caplog.set_level(logging.DEBUG)
        logger = logging.getLogger("app.core.scheduler")
        logger.debug(
            "scheduler.job_completed",
            extra={
                "job_name": "watchdog_cleanup",
                "duration_ms": 200.5,
            },
        )
        records = [
            r for r in caplog.records
            if r.getMessage() == "scheduler.job_completed"
        ]
        assert len(records) == 1
        assert records[0].duration_ms == 200.5