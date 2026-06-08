"""Deterministic extraction from saved project specs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.models.job import ExtractionMode, ExtractionSpec, Project


@dataclass
class ExtractedPayload:
    raw_data: dict[str, Any]
    normalized_data: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def _selected_fields(spec: ExtractionSpec) -> list[dict[str, Any]]:
    return [field for field in spec.fields or [] if field.get("selected")]


def _field_key(field: dict[str, Any]) -> str:
    return str(field.get("user_label") or field.get("label") or field.get("name") or "field")


def _text(tag: Tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(separator=" ", strip=True)).strip()


def _element_value(tag: Tag, field_type: str, source_url: str) -> str | None:
    field_type = field_type.lower()
    if field_type in {"url", "link"}:
        href = tag.get("href")
        if href:
            return urljoin(source_url, str(href))
    if field_type in {"image", "img"}:
        for attr in ("src", "data-src", "data-original", "srcset"):
            value = tag.get(attr)
            if value:
                first = str(value).split(",")[0].strip().split(" ")[0]
                return urljoin(source_url, first)
    for attr in ("content", "value", "title", "alt", "aria-label"):
        value = tag.get(attr)
        if value:
            return str(value).strip()
    text = _text(tag)
    return text or None


def _coerce_value(value: str | None, field_type: str) -> Any:
    if value is None:
        return None
    field_type = field_type.lower()
    if field_type == "number":
        cleaned = re.sub(r"[^0-9.,+-]", "", value).replace(",", "")
        try:
            return float(cleaned) if "." in cleaned else int(cleaned)
        except ValueError:
            return value
    if field_type == "boolean":
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "available", "in stock"}:
            return True
        if lowered in {"false", "no", "0", "unavailable", "out of stock"}:
            return False
    return value


def _relative_selector(selector: str, repeated_selector: str | None) -> str:
    if not repeated_selector:
        return selector
    stripped = selector.strip()
    repeated = repeated_selector.strip()
    if stripped.startswith(repeated):
        stripped = stripped[len(repeated) :].strip()
        if stripped.startswith(">"):
            stripped = stripped[1:].strip()
        return stripped or selector
    return selector


def _select_values(scope: BeautifulSoup | Tag, field: dict[str, Any], source_url: str) -> tuple[list[str | None], list[str]]:
    selector = field.get("selector")
    if not selector:
        return [], [f"{_field_key(field)} has no selector."]
    try:
        elements = scope.select(str(selector))
    except Exception as exc:
        return [], [f"{_field_key(field)} selector is invalid: {exc}"]
    field_type = str(field.get("type") or "string")
    return [_element_value(element, field_type, source_url) for element in elements], []


def _extract_from_repeated_containers(
    soup: BeautifulSoup,
    *,
    source_url: str,
    project: Project,
    spec: ExtractionSpec,
    fields: list[dict[str, Any]],
    max_records: int,
) -> list[ExtractedPayload]:
    analysis = project.analysis or {}
    repeated_selector = analysis.get("repeated_item_selector")
    if not repeated_selector:
        return []
    try:
        containers = soup.select(str(repeated_selector))[:max_records]
    except Exception:
        return []
    if not containers:
        return []

    payloads: list[ExtractedPayload] = []
    for container in containers:
        raw: dict[str, Any] = {"source_url": source_url}
        normalized: dict[str, Any] = {"source_url": source_url}
        warnings: list[str] = []
        present = 0
        missing_required = False
        for field in fields:
            selector = field.get("selector")
            if selector:
                scoped = dict(field)
                scoped["selector"] = _relative_selector(str(selector), str(repeated_selector))
            else:
                scoped = field
            values, field_warnings = _select_values(container, scoped, source_url)
            warnings.extend(field_warnings)
            value = next((item for item in values if item not in (None, "")), None)
            key = _field_key(field)
            raw[key] = value
            normalized[key] = _coerce_value(value, str(field.get("type") or "string"))
            if value not in (None, ""):
                present += 1
            elif field.get("required"):
                missing_required = True
                warnings.append(f"{key} is required but missing on this record.")
        if present and not missing_required:
            payloads.append(ExtractedPayload(raw, normalized, warnings))
    return payloads


def _extract_by_field_index(
    soup: BeautifulSoup,
    *,
    source_url: str,
    fields: list[dict[str, Any]],
    max_records: int,
) -> list[ExtractedPayload]:
    values_by_key: dict[str, tuple[dict[str, Any], list[str | None]]] = {}
    global_warnings: list[str] = []
    row_count = 0
    for field in fields:
        values, warnings = _select_values(soup, field, source_url)
        global_warnings.extend(warnings)
        row_count = max(row_count, len(values))
        values_by_key[_field_key(field)] = (field, values)

    row_count = min(row_count, max_records)
    payloads: list[ExtractedPayload] = []
    for index in range(row_count):
        raw: dict[str, Any] = {"source_url": source_url}
        normalized: dict[str, Any] = {"source_url": source_url}
        warnings = list(global_warnings)
        present = 0
        missing_required = False
        for key, (field, values) in values_by_key.items():
            value = values[index] if index < len(values) else None
            raw[key] = value
            normalized[key] = _coerce_value(value, str(field.get("type") or "string"))
            if value not in (None, ""):
                present += 1
            elif field.get("required"):
                missing_required = True
                warnings.append(f"{key} is required but missing on this record.")
        minimum_present = 1 if len(fields) <= 2 else 2
        if present >= minimum_present and not missing_required:
            payloads.append(ExtractedPayload(raw, normalized, warnings))
    return payloads


def _extract_content(
    soup: BeautifulSoup,
    *,
    source_url: str,
    spec: ExtractionSpec,
    fields: list[dict[str, Any]],
) -> list[ExtractedPayload]:
    selector = (spec.content_config or {}).get("primary_selector")
    content_scope: Tag | BeautifulSoup | None = None
    warnings: list[str] = []
    if selector:
        try:
            matches = soup.select(str(selector))
            content_scope = matches[0] if matches else None
        except Exception as exc:
            warnings.append(f"Primary content selector is invalid: {exc}")
    if content_scope is None:
        content_scope = soup.find("main") or soup.find("article") or soup.find("body") or soup

    text = re.sub(r"\s+", " ", content_scope.get_text(separator=" ", strip=True)).strip()
    raw: dict[str, Any] = {"source_url": source_url, "content": text}
    normalized: dict[str, Any] = {"source_url": source_url, "content": text}
    for field in fields:
        values, field_warnings = _select_values(soup, field, source_url)
        warnings.extend(field_warnings)
        value = next((item for item in values if item not in (None, "")), None)
        key = _field_key(field)
        raw[key] = value
        normalized[key] = _coerce_value(value, str(field.get("type") or "string"))
    return [ExtractedPayload(raw, normalized, warnings)] if text else []


def extract_records_from_html(
    html: str,
    *,
    source_url: str,
    project: Project,
    spec: ExtractionSpec,
    max_records: int = 1000,
) -> list[ExtractedPayload]:
    """Execute the saved extraction spec against one HTML document."""
    soup = BeautifulSoup(html, "lxml")
    fields = _selected_fields(spec)
    if spec.mode == ExtractionMode.CONTENT:
        return _extract_content(soup, source_url=source_url, spec=spec, fields=fields)
    if not fields:
        return []

    grouped = _extract_from_repeated_containers(
        soup,
        source_url=source_url,
        project=project,
        spec=spec,
        fields=fields,
        max_records=max_records,
    )
    if grouped:
        return grouped
    return _extract_by_field_index(soup, source_url=source_url, fields=fields, max_records=max_records)
