from datetime import datetime, timezone

import pytest

from app.models.job import ExtractionMode, ExtractionSpec, Project, ProjectState, RenderMode, WorkflowMode
from app.services.extractor import extract_records_from_html
from app.services.extraction_spec_service import default_spec_from_analysis, selected_field_count
from app.services.project_preview import build_preview_payload
from app.services.url_normalizer import discover_same_site_links, normalize_url


def _project(analysis: dict, mode: ExtractionMode = ExtractionMode.STRUCTURED) -> Project:
    return Project(
        id=1,
        user_id=1,
        url="https://example.com/products",
        extraction_mode=mode,
        workflow_mode=WorkflowMode.GUIDED,
        render_mode=RenderMode.AUTO,
        state=ProjectState.ANALYSIS_READY,
        confidence=0.91,
        warnings=["Review relative URLs"],
        analysis=analysis,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("confidence,selected", [(0.9, True), (0.69, False)])
def test_default_structured_spec_preserves_field_metadata(confidence, selected):
    project = _project(
        {
            "candidate_fields": [
                {
                    "name": "price",
                    "label": "Price",
                    "selector": ".price",
                    "data_type": "number",
                    "required": True,
                    "confidence": confidence,
                    "sample_values": ["$10"],
                }
            ]
        }
    )

    spec = default_spec_from_analysis(project)

    assert spec["mode"] == ExtractionMode.STRUCTURED
    field = spec["fields"][0]
    assert field["name"] == "price"
    assert field["user_label"] == "Price"
    assert field["selector"] == ".price"
    assert field["type"] == "number"
    assert field["selected"] is selected
    assert field["required"] is True
    assert field["sample_values"] == ["$10"]


def test_default_content_spec_preserves_content_config():
    project = _project(
        {
            "content_type": "documentation",
            "primary_content_selector": "main",
            "recommended_chunking": "section",
            "metadata_fields": [],
        },
        mode=ExtractionMode.CONTENT,
    )

    spec = default_spec_from_analysis(project)

    assert spec["mode"] == ExtractionMode.CONTENT
    assert spec["content_config"]["primary_selector"] == "main"
    assert spec["content_config"]["recommended_chunking"] == "section"
    assert spec["content_config"]["content_type"] == "documentation"


def test_preview_uses_selected_fields_only_and_reports_missing_samples():
    project = _project({})
    spec = ExtractionSpec(
        id=1,
        project_id=project.id,
        mode=ExtractionMode.STRUCTURED,
        fields=[
            {
                "name": "title",
                "label": "Title",
                "user_label": "Book title",
                "selector": "h3 a",
                "type": "string",
                "selected": True,
                "required": True,
                "confidence": 0.99,
                "sample_values": ["A", "B"],
                "warnings": [],
            },
            {
                "name": "unused",
                "label": "Unused",
                "user_label": "Unused",
                "selector": ".unused",
                "type": "string",
                "selected": False,
                "required": False,
                "confidence": 0.2,
                "sample_values": ["hidden"],
                "warnings": [],
            },
            {
                "name": "price",
                "label": "Price",
                "user_label": "Price",
                "selector": ".price",
                "type": "string",
                "selected": True,
                "required": True,
                "confidence": 0.9,
                "sample_values": [],
                "warnings": [],
            },
        ],
        content_config={},
        url_patterns=[],
        page_limit=50,
        export_format="csv",
    )

    preview = build_preview_payload(project, spec)

    assert preview["sample_records"] == [
        {"source_url": project.url, "Book title": "A", "Price": None},
        {"source_url": project.url, "Book title": "B", "Price": None},
    ]
    assert preview["missing_fields"][0]["name"] == "price"
    assert preview["quality_summary"]["selected_field_count"] == 2
    assert selected_field_count(spec) == 2


def test_selector_extractor_groups_records_by_repeated_container():
    project = _project({"repeated_item_selector": "article.product"})
    spec = ExtractionSpec(
        id=1,
        project_id=project.id,
        mode=ExtractionMode.STRUCTURED,
        fields=[
            {
                "name": "title",
                "label": "Title",
                "user_label": "Title",
                "selector": "article.product h3 a",
                "type": "string",
                "selected": True,
                "required": True,
                "confidence": 0.99,
                "sample_values": [],
                "warnings": [],
            },
            {
                "name": "price",
                "label": "Price",
                "user_label": "Price",
                "selector": ".price",
                "type": "number",
                "selected": True,
                "required": True,
                "confidence": 0.99,
                "sample_values": [],
                "warnings": [],
            },
            {
                "name": "detail",
                "label": "Detail",
                "user_label": "Detail URL",
                "selector": "h3 a",
                "type": "url",
                "selected": True,
                "required": False,
                "confidence": 0.99,
                "sample_values": [],
                "warnings": [],
            },
        ],
        content_config={},
        url_patterns=[],
        page_limit=50,
        export_format="csv",
    )
    html = """
    <article class="product"><h3><a href="/a">Alpha</a></h3><p class="price">$12.50</p></article>
    <article class="product"><h3><a href="/b">Beta</a></h3><p class="price">$9</p></article>
    """

    records = extract_records_from_html(html, source_url="https://example.com/list", project=project, spec=spec)

    assert [record.normalized_data["Title"] for record in records] == ["Alpha", "Beta"]
    assert records[0].normalized_data["Price"] == 12.5
    assert records[1].normalized_data["Detail URL"] == "https://example.com/b"


def test_url_normalizer_discovers_same_site_links_and_strips_tracking_params():
    html = """
    <a href="/page/?utm_source=x&id=1#top">Page</a>
    <a href="https://other.example/item">Other</a>
    <a href="mailto:test@example.com">Email</a>
    """

    assert normalize_url("https://example.com/a/?utm_medium=x&q=ok#frag") == "https://example.com/a?q=ok"
    assert discover_same_site_links(
        html,
        page_url="https://example.com/start",
        root_url="https://example.com/start",
    ) == ["https://example.com/page?id=1"]
