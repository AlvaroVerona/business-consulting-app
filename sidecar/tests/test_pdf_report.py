from pypdf import PdfReader
from reportlab.platypus import Paragraph
import io

from src.database.repository import Repository
from src.reports.pdf_report import _action_plan, _business_performance, _strategic_options, _styles, generate_pdf_report
from src.reports.report_context import build_report_context
from src.schemas.deep_analysis import ActionPlanItem, BusinessPerformanceSummary, StrategicOption
from tests.report_fixtures import seed_full_project


class _FakeSynthesis:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeContext:
    def __init__(self, synthesis):
        self.synthesis = synthesis


def test_full_report_is_valid_pdf_with_expected_content(db_session):
    repo = Repository(db_session)
    project_id = seed_full_project(repo)
    ctx = build_report_context(repo, project_id)

    pdf_bytes = generate_pdf_report(ctx)

    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2

    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Acme Wine Bar" in full_text
    assert "Gross margin compression" in full_text
    assert "Operating cost efficiency improving" in full_text
    assert "McKinsey" in full_text  # disclaimer present


def test_action_plan_table_cells_wrap_long_text():
    """Regression: 90-Day Action Plan table cells used to be plain strings,
    which reportlab's Table does not reliably word-wrap within a fixed
    column width — confirmed live: long LLM-authored action/data-required
    text overlapped adjacent cells instead of wrapping onto multiple lines.
    Cells must be Paragraph flowables, which do wrap."""
    styles = _styles()
    long_text = "Investigate COGS inflation due to supplier price increases or a shift in input mix towards higher-cost materials or labor-intensive products" * 2
    item = ActionPlanItem(action=long_text, data_requirements=long_text, kpi="Gross margin %", expected_impact=long_text)
    ctx = _FakeContext(_FakeSynthesis(ninety_day_plan=[item]))

    flowables = _action_plan(ctx, styles)
    table = next(f for f in flowables if hasattr(f, "_cellvalues"))
    body_row = table._cellvalues[1]

    assert all(isinstance(cell, Paragraph) for cell in body_row)


def test_business_performance_table_cells_wrap_long_text():
    styles = _styles()
    long_text = "declining, driven primarily by rising cost of goods sold relative to a flat revenue base across the period observed" * 2
    bp = BusinessPerformanceSummary(revenue="flat", growth="0%", margin=long_text, cash="not covered", key_operational_metrics=[])
    ctx = _FakeContext(_FakeSynthesis(business_performance=bp))

    flowables = _business_performance(ctx, styles)
    table = next(f for f in flowables if hasattr(f, "_cellvalues"))

    assert all(isinstance(row[1], Paragraph) for row in table._cellvalues)


def test_strategic_option_blank_recommendation_shows_placeholder():
    """Regression: an LLM sometimes returns "" for a required-but-optional
    field like recommendation (observed live) — rendering it verbatim left a
    blank line that reads as a bug even though it isn't one."""
    styles = _styles()
    option = StrategicOption(
        option="Renegotiate supplier contract", upside="Lower COGS", downside="Strains relationship",
        investment="Low", feasibility="MEDIUM", risks="Supplier may refuse", recommendation="",
    )
    ctx = _FakeContext(_FakeSynthesis(strategic_options=[option]))

    flowables = _strategic_options(ctx, styles)
    recommendation_paragraph = next(f.text for f in flowables if isinstance(f, Paragraph) and "Recommendation" in f.text)

    assert "(not stated)" in recommendation_paragraph


def test_does_not_crash_on_llm_text_containing_markup_like_characters(db_session):
    """Regression: reportlab's Paragraph runs its content through a mini-XML
    parser (that's how our own <b>/<font> tags work), so unescaped LLM- or
    user-authored text containing '<', '>', or '&' that looks like a tag
    crashed report generation. Reproduced live with company name "Smith &
    Sons" and concern text mentioning "the <b> tag"."""
    repo = Repository(db_session)
    company = repo.create_company(name="Smith & Sons Wine Bar")
    project = repo.create_project(company.id, name="P1 <2026>")
    repo.create_concern(
        project_id=project.id,
        title="Margin & cost issue",
        severity="HIGH",
        confidence="HIGH",
        business_impact="Use the <b> tag pattern & other markup-like text here.",
        recommended_action="Review COGS < revenue ratio & renegotiate.",
    )

    ctx = build_report_context(repo, project.id)

    pdf_bytes = generate_pdf_report(ctx)  # must not raise

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Smith & Sons Wine Bar" in full_text
    assert "Use the <b> tag pattern" in full_text


def test_report_with_no_completed_run_does_not_crash(db_session):
    repo = Repository(db_session)
    company = repo.create_company(name="Acme")
    project = repo.create_project(company.id, name="P1")
    ctx = build_report_context(repo, project.id)

    pdf_bytes = generate_pdf_report(ctx)

    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "No Deep Analysis run has completed" in full_text
