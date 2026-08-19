from sqlalchemy.orm import Session

from src.database.models import ChatMessage, Company, Document, DocumentChunk, Finding, Project


class Repository:
    """Thin CRUD layer. Keeps SQLAlchemy session handling out of the API
    routes and the services that need persistence."""

    def __init__(self, db: Session):
        self.db = db

    # --- companies ---------------------------------------------------

    def create_company(self, name: str, industry: str | None = None, notes: str | None = None) -> Company:
        company = Company(name=name, industry=industry, notes=notes)
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def list_companies(self) -> list[Company]:
        return self.db.query(Company).order_by(Company.created_at.desc()).all()

    def get_company(self, company_id: int) -> Company | None:
        return self.db.get(Company, company_id)

    # --- projects ------------------------------------------------------

    def create_project(self, company_id: int, name: str, description: str | None = None) -> Project:
        project = Project(company_id=company_id, name=name, description=description)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_projects(self, company_id: int) -> list[Project]:
        return (
            self.db.query(Project)
            .filter(Project.company_id == company_id)
            .order_by(Project.created_at.desc())
            .all()
        )

    def get_project(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)

    # --- documents -------------------------------------------------------

    def create_document(self, project_id: int, filename: str, file_type: str, storage_path: str) -> Document:
        document = Document(
            project_id=project_id,
            filename=filename,
            file_type=file_type,
            storage_path=storage_path,
            status="INGESTED",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_document(self, document_id: int) -> Document | None:
        return self.db.get(Document, document_id)

    def set_document_status(self, document_id: int, status: str, error: str | None = None) -> None:
        document = self.db.get(Document, document_id)
        if document is None:
            return
        document.status = status
        document.error = error
        self.db.commit()

    def add_chunks(self, document_id: int, chunks: list[dict]) -> None:
        for i, chunk in enumerate(chunks):
            self.db.add(
                DocumentChunk(
                    document_id=document_id,
                    order_index=i,
                    content=chunk["content"],
                    location=chunk.get("location"),
                )
            )
        self.db.commit()

    def list_documents(self, project_id: int) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
            .all()
        )

    def list_chunks(self, project_id: int) -> list[DocumentChunk]:
        return (
            self.db.query(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(Document.project_id == project_id)
            .all()
        )

    # --- findings ---------------------------------------------------------

    def create_finding(self, project_id: int, **fields) -> Finding:
        finding = Finding(project_id=project_id, **fields)
        self.db.add(finding)
        self.db.commit()
        self.db.refresh(finding)
        return finding

    def list_findings(self, project_id: int) -> list[Finding]:
        return (
            self.db.query(Finding)
            .filter(Finding.project_id == project_id)
            .order_by(Finding.created_at.desc())
            .all()
        )

    # --- chat ---------------------------------------------------------

    def add_chat_message(
        self, project_id: int, role: str, content: str, finding_ids: list[int] | None = None
    ) -> ChatMessage:
        message = ChatMessage(project_id=project_id, role=role, content=content, finding_ids=finding_ids)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_chat_messages(self, project_id: int) -> list[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.project_id == project_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
