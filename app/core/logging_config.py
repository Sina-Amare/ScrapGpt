"""Logging configuration: formatters, filters, and setup.

Called as the first statement in main.py's lifespan, before any
service imports.  Configures the root logger with stdout output,
a DevFormatter (text) or JsonFormatter depending on LOG_FORMAT,
and two filters:

- ContextInjectingFilter: reads contextvars and injects them
  into every LogRecord so existing logger.info("event", extra={})
  calls automatically gain ambient context.

- SecretRedactingFilter: backstop that strips known API key
  patterns from log messages.  Does not replace call-site
  discipline — it is a safety net.

disable_existing_loggers=False preserves all existing
logging.getLogger(__name__) declarations in service files.
"""

from __future__ import annotations

import json
import logging
import logging.config
import sys
from datetime import datetime, timezone

from app.core.config import settings
from app.core.log_context import get_log_context
from app.services.provider_service import redact_provider_secret


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class ContextInjectingFilter(logging.Filter):
    """Inject contextvars (request_id, user_id, project_id, page_id)
    into every LogRecord before formatting.

    Existing extra={} fields on the record are not overwritten —
    call-site context takes precedence over ambient context.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in get_log_context().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class SecretRedactingFilter(logging.Filter):
    """Backstop filter that strips known API key patterns from
    log messages and args.  Does not replace call-site discipline
    (safe_provider_error_message) — it is a safety net for cases
    where redaction was missed.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_provider_secret(str(record.msg))
        if record.args:
            record.args = tuple(
                redact_provider_secret(str(a))
                if isinstance(a, str)
                else a
                for a in (
                    record.args
                    if isinstance(record.args, tuple)
                    else (record.args,)
                )
            )
        return True


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class DevFormatter(logging.Formatter):
    """Human-readable formatter for local development.

    Output format:
    2026-06-10T14:23:01.412Z INFO  app.services.analyzer \
        analyzer.completed confidence=0.87 mode=structured

    Timestamp, level (fixed width), logger name, event name,
    then key=value pairs from extra={}.  No color dependency
    (works over SSH).
    """

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp in ISO 8601 UTC
        ts = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Fixed-width level
        level = record.levelname.ljust(5)

        # Logger name (shortened to last two segments)
        logger_name = record.name
        parts = logger_name.split(".")
        if len(parts) > 2:
            logger_name = ".".join(parts[-2:])

        # Core message
        message = record.getMessage()

        # Build key=value string from extra fields
        # (skip standard LogRecord attributes)
        standard_attrs = set(
            logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__.keys()
        ) | {"message", "asctime"}
        kv_parts: list[str] = []
        for key, value in record.__dict__.items():
            if key not in standard_attrs and value is not None:
                kv_parts.append(f"{key}={value}")
        kv = " ".join(kv_parts)

        # Combine
        base = f"{ts} {level} {logger_name} {message}"
        if kv:
            base = f"{base} {kv}"

        # Append exception info if present
        if record.exc_info and record.exc_text is None:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            base = f"{base}\n{record.exc_text}"

        return base


class JsonFormatter(logging.Formatter):
    """JSON formatter for production / Docker deployment.

    One JSON object per line.  Parseable by every log aggregator
    without regex.  The extra={} context dicts that already exist
    on every log call map directly to top-level JSON fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp in ISO 8601 UTC
        ts = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat(timespec="milliseconds") + "Z"

        # Core fields
        log_obj: dict = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add all extra fields as top-level JSON keys
        standard_attrs = set(
            logging.LogRecord(
                "", 0, "", 0, "", (), None
            ).__dict__.keys()
        ) | {"message", "asctime"}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and value is not None:
                log_obj[key] = value

        # Add exception info
        if record.exc_info:
            log_obj["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(log_obj, default=str)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure the root logger and bridge third-party stdlib loggers.

    Called as the very first statement in main.py's lifespan.
    Idempotent — calling twice produces the same result.
    """

    if settings.LOG_FORMAT == "json":
        formatter_class = (
            "app.core.logging_config.JsonFormatter"
        )
    else:
        formatter_class = (
            "app.core.logging_config.DevFormatter"
        )

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": formatter_class,
            }
        },
        "filters": {
            "context_injector": {
                "()": "app.core.logging_config"
                ".ContextInjectingFilter",
            },
            "secret_redactor": {
                "()": "app.core.logging_config"
                ".SecretRedactingFilter",
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "default",
                "filters": [
                    "context_injector",
                    "secret_redactor",
                ],
            }
        },
        "root": {
            "handlers": ["stdout"],
            "level": settings.LOG_LEVEL.upper(),
        },
        "loggers": {
            "uvicorn.access": {"level": "WARNING"},
            "uvicorn.error": {"level": "INFO"},
            "sqlalchemy.engine": {"level": "WARNING"},
            "apscheduler": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "litellm": {"level": "WARNING"},
        },
    }

    logging.config.dictConfig(config)