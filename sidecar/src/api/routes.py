import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.database.repository import Repository
from src.ingestion.registry import UnsupportedFileType, parse_document
from src.llm.router import get_llm_client
from src.schemas.chat import ChatRequest, QuickAnswer
from src.schemas.company import CompanyCreate, CompanyOut
from src.schemas.document import DocumentOut
from src.schemas.evidence import Citation, FindingOut
from src.schemas.project import ProjectCreate, ProjectOut
from src.services.quick_answer_service import QuickAnswerService
from src.storage import extension_of, save_upload

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
    return [
        FindingOut(
            id=f.id,
            statement=f.statement,
            source_type=f.source_type,
            confidence=f.confidence,
            citation=Citation(document_id=f.document_id, chunk_id=f.chunk_id, location=f.location),
            calculation=f.calculation,
            assumption=f.assumption,
        )
        for f in repo.list_findings(project_id)
    ]


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
