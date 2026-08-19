from dataclasses import dataclass
from datetime import datetime, timezone

from src.database.models import BusinessProfile, Company, Concern, DeepAnalysisRun, Hypothesis, Opportunity, Project
from src.database.repository import Repository
from src.schemas.deep_analysis import ExecutiveSynthesisDraft
from src.services.financial_analysis_service import FinancialAnalysisResult, FinancialAnalysisService


class ProjectNotFound(ValueError):
    pass


@dataclass
class ReportContext:
    """Everything a report generator (PDF/PPTX/Excel) needs, already
    validated by the services that produced it — no LLM calls happen while
    building or rendering a report. `synthesis` is None when no Deep
    Analysis run has completed yet; generators render what's available and
    say so, rather than blocking the export on a run existing."""

    company: Company
    project: Project
    run: DeepAnalysisRun | None
    synthesis: ExecutiveSynthesisDraft | None
    business_profile: BusinessProfile | None
    financial_analysis: FinancialAnalysisResult
    concerns: list[Concern]
    opportunities: list[Opportunity]
    hypotheses: list[Hypothesis]
    generated_at: datetime


def build_report_context(repo: Repository, project_id: int) -> ReportContext:
    project = repo.get_project(project_id)
    if project is None:
        raise ProjectNotFound(f"Project {project_id} not found")

    company = repo.get_company(project.company_id)

    run = next((r for r in repo.list_deep_analysis_runs(project_id) if r.status == "COMPLETED"), None)
    synthesis = ExecutiveSynthesisDraft(**run.executive_summary) if run is not None else None

    return ReportContext(
        company=company,
        project=project,
        run=run,
        synthesis=synthesis,
        business_profile=repo.get_latest_business_profile(project_id),
        financial_analysis=FinancialAnalysisService(repo).run(project_id),
        concerns=repo.list_concerns(project_id),
        opportunities=repo.list_opportunities(project_id),
        hypotheses=repo.list_hypotheses(project_id),
        generated_at=datetime.now(timezone.utc),
    )
