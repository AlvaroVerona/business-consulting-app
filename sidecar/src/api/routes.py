import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.analysis.scenario import ScenarioAdjustment
from src.database.database import get_db
from src.database.models import Finding
from src.database.repository import Repository
from src.ingestion.registry import UnsupportedFileType, parse_document
from src.llm.router import get_llm_client
from src.reports.excel_export import generate_excel_export
from src.reports.pdf_report import generate_pdf_report
from src.reports.pptx_report import generate_pptx_report
from src.reports.report_context import ProjectNotFound, build_report_context
from src.schemas.business_profile import BusinessProfileOut
from src.schemas.chat import ChatRequest, QuickAnswer
from src.schemas.company import CompanyCreate, CompanyOut
from src.schemas.concern import ConcernOut
from src.schemas.deep_analysis import DeepAnalysisRunOut
from src.schemas.document import DocumentOut
from src.schemas.evidence import Citation, FindingOut
from src.schemas.financial import FinancialAnalysisOut, PeriodMetricsOut
from src.schemas.hypothesis import HypothesisCreate, HypothesisOut, HypothesisUpdate
from src.schemas.issue_tree import IssueNodeOut, IssueTreeOut, IssueTreeRequest
from src.schemas.monitoring import MonitoringEventOut
from src.schemas.opportunity import OpportunityOut
from src.schemas.project import ProjectCreate, ProjectOut
from src.schemas.scenario import ScenarioRequest, ScenarioResultOut
from src.services.business_understanding_agent import BusinessUnderstandingAgent
from src.services.concern_detection_service import ConcernDetectionService
from src.services.deep_analysis_orchestrator import DeepAnalysisOrchestrator
from src.services.financial_analysis_service import FinancialAnalysisService
from src.services.issue_tree_service import IssueTreeService
from src.services.opportunity_detection_service import OpportunityDetectionService
from src.services.quick_answer_service import QuickAnswerService
from src.services.scenario_service import ScenarioService
from src.storage import extension_of, save_upload


class DeepAnalysisRequest(BaseModel):
    use_claude: bool = False  # explicit opt-in; see llm/router.py — local Ollama is the default


def _finding_to_out(f: Finding) -> FindingOut:
    return FindingOut(
        id=f.id,
        statement=f.statement,
        source_type=f.source_type,
        confidence=f.confidence,
        citation=Citation(document_id=f.document_id, chunk_id=f.chunk_id, location=f.location),
        calculation=f.calculation,
        assumption=f.assumption,
        origin=f.origin,
    )


def _period_to_out(p) -> PeriodMetricsOut:
    return PeriodMetricsOut(
        period=p.period,
        revenue=p.revenue,
        cogs=p.cogs,
        opex=p.opex,
        ebitda=p.ebitda,
        ebitda_is_implied=p.ebitda_is_implied,
        gross_margin=p.gross_margin,
        ebitda_margin=p.ebitda_margin,
        opex_ratio=p.opex_ratio,
    )


def _issue_nodes_to_out(nodes: list, parent_id: int | None) -> list[IssueNodeOut]:
    children = sorted((n for n in nodes if n.parent_id == parent_id), key=lambda n: n.order_index)
    return [
        IssueNodeOut(
            id=n.id,
            label=n.label,
            is_forced_mece=n.is_forced_mece,
            overlap_note=n.overlap_note,
            children=_issue_nodes_to_out(nodes, n.id),
        )
        for n in children
    ]


def _issue_tree_to_out(tree, nodes: list) -> IssueTreeOut:
    return IssueTreeOut(
        id=tree.id,
        project_id=tree.project_id,
        question=tree.question,
        overall_note=tree.overall_note,
        root_children=_issue_nodes_to_out(nodes, None),
        created_at=tree.created_at,
    )

logger = logging.getLogger(__name__)
router = APIRouter()


def get_repo(db: Session = Depends(get_db)) -> Repository:
    return Repository(db)


# --- companies -------------------------------------------------------------


@router.post("/companies", response_model=CompanyOut)
def create_company(payload: CompanyCreate, repo: Repository = Depends(get_repo)):
    return repo.create_company(name=payload.name, industry=payload.industry, notes=payload.notes)


@router.get("/companies", response_model=list[CompanyOut])
def list_companies(repo: Repository = Depends(get_repo)):
    return repo.list_companies()


# --- projects ----------------------------------------------------------------


@router.post("/companies/{company_id}/projects", response_model=ProjectOut)
def create_project(company_id: int, payload: ProjectCreate, repo: Repository = Depends(get_repo)):
    if repo.get_company(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")

    return repo.create_project(company_id=company_id, name=payload.name, description=payload.description)


@router.get("/companies/{company_id}/projects", response_model=list[ProjectOut])
def list_projects(company_id: int, repo: Repository = Depends(get_repo)):
    return repo.list_projects(company_id)


# --- documents -----------------------------------------------------------------


@router.post("/projects/{project_id}/documents", response_model=DocumentOut)
def upload_document(project_id: int, file: UploadFile, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    extension = extension_of(file.filename)
    content = file.file.read()
    path = save_upload(project_id, file.filename, content)

    document = repo.create_document(
        project_id=project_id,
        filename=file.filename,
        file_type=extension.lstrip("."),
        storage_path=path,
    )

    try:
        chunks = parse_document(path, extension)
        repo.add_chunks(document.id, chunks)
        repo.set_document_status(document.id, "INDEXED")
    except UnsupportedFileType as e:
        repo.set_document_status(document.id, "FAILED", error=str(e))
    except Exception as e:  # noqa: BLE001 — surface parser failures on the document, don't 500 the upload
        logger.exception("Failed to parse document %s", document.id)
        repo.set_document_status(document.id, "FAILED", error=str(e))

    return repo.get_document(document.id)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(project_id: int, repo: Repository = Depends(get_repo)):
    return repo.list_documents(project_id)


# --- findings ------------------------------------------------------------------


@router.get("/projects/{project_id}/findings", response_model=list[FindingOut])
def list_findings(project_id: int, repo: Repository = Depends(get_repo)):
    return [_finding_to_out(f) for f in repo.list_findings(project_id)]


# --- financial analysis (deterministic engine, spec section 13) ----------------


@router.post("/projects/{project_id}/analysis/financial", response_model=FinancialAnalysisOut)
def run_financial_analysis(project_id: int, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = FinancialAnalysisService(repo).run(project_id)

    return FinancialAnalysisOut(
        periods=[_period_to_out(p) for p in result.periods],
        revenue_trend=result.revenue_trend,
        gross_margin_trend=result.gross_margin_trend,
        ebitda_margin_trend=result.ebitda_margin_trend,
        findings=[_finding_to_out(f) for f in result.findings],
    )


# --- hypotheses (spec section 4) ------------------------------------------------


@router.post("/projects/{project_id}/hypotheses", response_model=HypothesisOut)
def create_hypothesis(project_id: int, payload: HypothesisCreate, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return repo.create_hypothesis(
        project_id=project_id,
        statement=payload.statement,
        status=payload.status.value,
        supporting_finding_ids=payload.supporting_finding_ids,
        contradicting_finding_ids=payload.contradicting_finding_ids,
        data_required=payload.data_required,
        business_impact=payload.business_impact,
        priority=payload.priority,
        next_test=payload.next_test,
    )


@router.get("/projects/{project_id}/hypotheses", response_model=list[HypothesisOut])
def list_hypotheses(project_id: int, repo: Repository = Depends(get_repo)):
    return repo.list_hypotheses(project_id)


@router.patch("/hypotheses/{hypothesis_id}", response_model=HypothesisOut)
def update_hypothesis(hypothesis_id: int, payload: HypothesisUpdate, repo: Repository = Depends(get_repo)):
    if repo.get_hypothesis(hypothesis_id) is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    fields = payload.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] is not None:
        fields["status"] = payload.status.value

    return repo.update_hypothesis(hypothesis_id, **fields)


# --- concerns / opportunities (spec section 4) ----------------------------------


@router.post("/projects/{project_id}/concerns/detect", response_model=list[ConcernOut])
def detect_concerns(project_id: int, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    analysis = FinancialAnalysisService(repo).run(project_id)
    return ConcernDetectionService(repo).run(project_id, analysis)


@router.get("/projects/{project_id}/concerns", response_model=list[ConcernOut])
def list_concerns(project_id: int, repo: Repository = Depends(get_repo)):
    return repo.list_concerns(project_id)


@router.post("/projects/{project_id}/opportunities/detect", response_model=list[OpportunityOut])
def detect_opportunities(project_id: int, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    analysis = FinancialAnalysisService(repo).run(project_id)
    return OpportunityDetectionService(repo).run(project_id, analysis)


@router.get("/projects/{project_id}/opportunities", response_model=list[OpportunityOut])
def list_opportunities(project_id: int, repo: Repository = Depends(get_repo)):
    return repo.list_opportunities(project_id)


# --- chat (Quick Answer mode) --------------------------------------------------


@router.post("/projects/{project_id}/chat", response_model=QuickAnswer)
def chat(project_id: int, payload: ChatRequest, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    repo.add_chat_message(project_id, role="user", content=payload.question)

    llm = get_llm_client(use_claude=payload.use_claude)
    service = QuickAnswerService(repo, llm)

    try:
        result = service.answer(project_id, payload.question)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    repo.add_chat_message(
        project_id,
        role="assistant",
        content=result.answer,
        finding_ids=[f.id for f in result.evidence],
    )

    return result


# --- business understanding (spec section 3 / 7) --------------------------------


@router.post("/projects/{project_id}/business-profile", response_model=BusinessProfileOut)
def run_business_understanding(project_id: int, payload: DeepAnalysisRequest, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    llm = get_llm_client(use_claude=payload.use_claude)

    try:
        return BusinessUnderstandingAgent(repo, llm).run(project_id)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/projects/{project_id}/business-profile", response_model=BusinessProfileOut | None)
def get_business_profile(project_id: int, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return repo.get_latest_business_profile(project_id)


# --- deep analysis (spec section 2 / 15 Phase 3) ---------------------------------


@router.post("/projects/{project_id}/deep-analysis", response_model=DeepAnalysisRunOut)
def run_deep_analysis(project_id: int, payload: DeepAnalysisRequest, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    llm = get_llm_client(use_claude=payload.use_claude)
    return DeepAnalysisOrchestrator(repo, llm).run(project_id)


@router.get("/projects/{project_id}/deep-analysis", response_model=list[DeepAnalysisRunOut])
def list_deep_analysis_runs(project_id: int, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return repo.list_deep_analysis_runs(project_id)


@router.get("/deep-analysis/{run_id}", response_model=DeepAnalysisRunOut)
def get_deep_analysis_run(run_id: int, repo: Repository = Depends(get_repo)):
    run = repo.get_deep_analysis_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Deep analysis run not found")
    return run


# --- professional outputs (spec section 15 Phase 4) -----------------------------


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip().replace(" ", "_") or "report"


def _attachment_headers(filename: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


@router.get("/projects/{project_id}/reports/pdf")
def get_pdf_report(project_id: int, repo: Repository = Depends(get_repo)):
    try:
        ctx = build_report_context(repo, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    filename = f"{_safe_filename(ctx.project.name)}_report.pdf"
    return Response(
        content=generate_pdf_report(ctx), media_type="application/pdf", headers=_attachment_headers(filename)
    )


@router.get("/projects/{project_id}/reports/pptx")
def get_pptx_report(project_id: int, repo: Repository = Depends(get_repo)):
    try:
        ctx = build_report_context(repo, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    filename = f"{_safe_filename(ctx.project.name)}_report.pptx"
    return Response(
        content=generate_pptx_report(ctx),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers=_attachment_headers(filename),
    )


@router.get("/projects/{project_id}/reports/excel")
def get_excel_export(project_id: int, repo: Repository = Depends(get_repo)):
    try:
        ctx = build_report_context(repo, project_id)
    except ProjectNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    filename = f"{_safe_filename(ctx.project.name)}_analysis.xlsx"
    return Response(
        content=generate_excel_export(ctx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_attachment_headers(filename),
    )


# --- scenario modeling (spec section 15 Phase 5) ---------------------------------


@router.post("/projects/{project_id}/scenarios", response_model=ScenarioResultOut)
def run_scenario(project_id: int, payload: ScenarioRequest, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    adjustments = [ScenarioAdjustment(field=a.field, kind=a.kind, value=a.value) for a in payload.adjustments]

    try:
        result = ScenarioService(repo).run(project_id, adjustments, base_period=payload.base_period)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return ScenarioResultOut(
        baseline=_period_to_out(result.baseline),
        scenario=_period_to_out(result.scenario),
        revenue_delta=result.revenue_delta,
        gross_margin_delta=result.gross_margin_delta,
        ebitda_margin_delta=result.ebitda_margin_delta,
    )


# --- monitoring (spec section 15 Phase 5) -----------------------------------------


@router.get("/projects/{project_id}/monitoring/events", response_model=list[MonitoringEventOut])
def list_monitoring_events(project_id: int, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return repo.list_monitoring_events(project_id)


# --- issue trees (spec section 4 / 15 Phase 3) ------------------------------------


@router.post("/projects/{project_id}/issue-trees", response_model=IssueTreeOut)
def create_issue_tree(project_id: int, payload: IssueTreeRequest, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    llm = get_llm_client(use_claude=payload.use_claude)

    try:
        tree = IssueTreeService(repo, llm).run(project_id, payload.question)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return _issue_tree_to_out(tree, repo.list_issue_nodes(tree.id))


@router.get("/projects/{project_id}/issue-trees", response_model=list[IssueTreeOut])
def list_issue_trees(project_id: int, repo: Repository = Depends(get_repo)):
    if repo.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    trees = repo.list_issue_trees(project_id)

    nodes_by_tree: dict[int, list] = {}
    for node in repo.list_issue_nodes_for_project(project_id):
        nodes_by_tree.setdefault(node.tree_id, []).append(node)

    return [_issue_tree_to_out(tree, nodes_by_tree.get(tree.id, [])) for tree in trees]


@router.get("/issue-trees/{tree_id}", response_model=IssueTreeOut)
def get_issue_tree(tree_id: int, repo: Repository = Depends(get_repo)):
    tree = repo.get_issue_tree(tree_id)
    if tree is None:
        raise HTTPException(status_code=404, detail="Issue tree not found")

    return _issue_tree_to_out(tree, repo.list_issue_nodes(tree.id))
