# ScrapGPT Logging Final Review

**Date:** 2026-06-10  
**Reviewed documents:**

- `docs/LOGGING_REVIEW.md`
- `docs/LOGGING_REMEDIATION_REPORT.md`
- `docs/LOGGING_IMPLEMENTATION_REPORT.md`

**Reviewed code:** logging infrastructure, request middleware, log context, crawl scope, project extraction, exception logging call sites, and logging tests.

## Verdict

**REJECT**

The remediation fixed the original blocker for normal `extra={...}` fields and raw URL fields, and it improved request cleanup and scope correlation. However, exception tracebacks still bypass the redaction path. Any `logger.exception()` event can emit raw exception text containing API keys, bearer tokens, signed URL query strings, or other secrets in the JSON `exception` field or text formatter traceback.

## Findings

### blocker - Exception tracebacks bypass secret redaction

`SecretRedactingFilter` redacts `record.msg`, `record.args`, and structured extra fields in `app/core/logging_config.py`. But both formatters create traceback text after the filter has already run:

- `DevFormatter.format()` calls `self.formatException(record.exc_info)` and appends `record.exc_text`.
- `JsonFormatter.format()` calls `self.formatException(record.exc_info)` and writes it to the `exception` field.

That formatted exception string is not passed through `redact_provider_secret()` or URL sanitization. I verified this with the actual `SecretRedactingFilter` + `JsonFormatter` / `DevFormatter` pipeline using an exception message containing `api_key=sk-...` and `https://example.com/path?token=secret`; both secrets appeared in output.

This matters because the code still uses `logger.exception()` in real paths:

- `app/services/project_extraction.py`
- `app/services/job_executor.py`
- `app/services/task_executor.py`
- `app/services/watchdog.py`

The logging security requirement is not satisfied until exception text is sanitized before emission.

### major - Remediation tests still miss the traceback leak

The new `tests/core/test_logging_remediation.py` improves coverage for `extra` fields, URL fields, request IDs, and scope correlation. It does not include a test where `exc_info` contains a secret-bearing exception message and the output is formatted through the real formatter pipeline.

`tests/core/test_logging_config.py` asserts that exception info is included, but not that it is sanitized. This is why the full suite passes while the blocker remains.

### major - Middleware tests partly replicate the implementation instead of invoking it

The request cleanup remediation exists in the real `app/main.py` middleware and appears correct: `clear_context()` is in `finally`, and `http.request_failed` is logged in `except`.

The remediation tests, however, mostly build local FastAPI apps with copied middleware logic or simulate the try/except/finally pattern directly. That reduces regression protection if `app.main.request_context_middleware` changes later. This is not the main rejection reason, but it is still a test quality gap.

### major - Project endpoint error logging remains intentionally deferred

The remediation report marks the prior project endpoint error-logging finding as "Not fixed". Generic `http.request` / `http.request_failed` logs help, but specific project endpoint conflict/error events are still incomplete. This is acceptable as deferred work only after the security blocker is fixed.

### minor - URL sanitization is conservative but lossy

URL fields now strip query strings and fragments, which fixes the leak class. The behavior is intentionally lossy: all query parameters are removed, including non-sensitive pagination/debug parameters. That is a reasonable security tradeoff for logs.

### observation - Original structured `extra` leak is materially fixed

For normal log records without `exc_info`, the remediation now redacts:

- known secret keys like `api_key`, `token`, `password`, `authorization`, and `api_key_encrypted`
- nested dict/list values
- URL fields such as `url`, `normalized_url`, `source_url`, and related keys
- ad-hoc string values starting with `http://` or `https://`

This directly addresses the original `extra`-field blocker except for exception traceback text.

### observation - Context propagation is improved

Scope confirmation events now accept and log `project_id`, and project extraction passes it in both confirmation checks. `set_page_context(page_id=...)` is now called in the extraction page loop, so nested logs can inherit page context after a page is selected.

## Verification Run

Commands run:

```powershell
venv\Scripts\python.exe -m pytest tests\core\test_logging_config.py tests\core\test_logging_remediation.py tests\core\test_log_context.py -q
venv\Scripts\python.exe -m pytest tests\ -x --tb=short -q
```

Results:

- Targeted logging tests: `61 passed`
- Full backend tests: `329 passed, 43 warnings`

Additional manual verification:

- Ran the actual `SecretRedactingFilter` + `JsonFormatter` / `DevFormatter` pipeline with `exc_info` containing `api_key=sk-...` and `?token=secret`.
- Result: both JSON and text outputs leaked the secret-bearing traceback text.

## Required Changes Before Approval

1. Sanitize formatted exception text in both `JsonFormatter` and `DevFormatter` before output.
2. Add tests proving `exc_info` with API keys, bearer tokens, and query-string tokens is redacted in JSON and text output.
3. Prefer tests that exercise the real `app.main` middleware instead of copied middleware logic.
4. Revisit the deferred project endpoint error-logging gaps after the logging security blocker is closed.
