from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.database.models import (
    BusinessProfile,
    ChatMessage,
    Company,
    Concern,
    DeepAnalysisRun,
    Document,
    DocumentChunk,
    Finding,
    Hypothesis,
    MonitoringEvent,
    Opportunity,
    Project,
)


def _utcnow():
    return datetime.now(timezone.utc)


# Spec section 15 Phase 2/Deep Analysis mode step 10: concerns/opportunities
# must be shown *prioritized*, not just in whatever order they were detected.
# Lower rank sorts first (most urgent/most confident first); an unrecognized
# value sorts last rather than raising, since a future rule could introduce a
# severity string these maps don't know about yet.
_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
_CONFIDENCE_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}


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
        # Ordered by upload time then in-document position — extract_periods
        # and QuickAnswerService both assume this is chronological order
        # (e.g. "first"/"last" period for a trend), which an unordered query
        # can't guarantee once a project has more than one document.
        return (
            self.db.query(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(Document.project_id == project_id)
            .order_by(Document.created_at, Document.id, DocumentChunk.order_index)
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

    # --- hypotheses -----------------------------------------------------

    def create_hypothesis(self, project_id: int, **fields) -> Hypothesis:
        fields.setdefault("supporting_finding_ids", [])
        fields.setdefault("contradicting_finding_ids", [])
        hypothesis = Hypothesis(project_id=project_id, **fields)
        self.db.add(hypothesis)
        self.db.commit()
        self.db.refresh(hypothesis)
        return hypothesis

    def get_hypothesis(self, hypothesis_id: int) -> Hypothesis | None:
        return self.db.get(Hypothesis, hypothesis_id)

    def update_hypothesis(self, hypothesis_id: int, **fields) -> Hypothesis | None:
        # Caller (routes.update_hypothesis) already filters to explicitly-set
        # fields via `model_dump(exclude_unset=True)` — every key present
        # here, including an explicit None, is an intentional write. Skipping
        # None here would make it impossible to ever clear a field via PATCH.
        hypothesis = self.db.get(Hypothesis, hypothesis_id)
        if hypothesis is None:
            return None
        for key, value in fields.items():
            setattr(hypothesis, key, value)
        self.db.commit()
        self.db.refresh(hypothesis)
        return hypothesis

    def list_hypotheses(self, project_id: int) -> list[Hypothesis]:
        return (
            self.db.query(Hypothesis)
            .filter(Hypothesis.project_id == project_id)
            .order_by(Hypothesis.created_at.desc())
            .all()
        )

    def clear_agent_hypotheses(self, project_id: int) -> None:
        # Only "agent"-origin rows: a user's manually created hypotheses
        # (origin="manual") are never auto-deleted by a deep-analysis re-run.
        self.db.query(Hypothesis).filter(
            Hypothesis.project_id == project_id, Hypothesis.origin == "agent"
        ).delete()
        self.db.commit()

    # --- concerns -----------------------------------------------------

    def create_concern(self, project_id: int, **fields) -> Concern:
        fields.setdefault("evidence_finding_ids", [])
        fields.setdefault("root_cause_hypothesis_ids", [])
        concern = Concern(project_id=project_id, **fields)
        self.db.add(concern)
        self.db.commit()
        self.db.refresh(concern)
        return concern

    def list_concerns(self, project_id: int) -> list[Concern]:
        concerns = self.db.query(Concern).filter(Concern.project_id == project_id).all()
        return sorted(
            concerns,
            key=lambda c: (_SEVERITY_RANK.get(c.severity, 99), -c.created_at.timestamp()),
        )

    def get_concern(self, concern_id: int) -> Concern | None:
        return self.db.get(Concern, concern_id)

    def update_concern(self, concern_id: int, **fields) -> Concern | None:
        concern = self.db.get(Concern, concern_id)
        if concern is None:
            return None
        for key, value in fields.items():
            setattr(concern, key, value)
        self.db.commit()
        self.db.refresh(concern)
        return concern

    def clear_concerns(self, project_id: int) -> None:
        self.db.query(Concern).filter(Concern.project_id == project_id).delete()
        self.db.commit()

    # --- opportunities --------------------------------------------------

    def create_opportunity(self, project_id: int, **fields) -> Opportunity:
        fields.setdefault("evidence_finding_ids", [])
        opportunity = Opportunity(project_id=project_id, **fields)
        self.db.add(opportunity)
        self.db.commit()
        self.db.refresh(opportunity)
        return opportunity

    def list_opportunities(self, project_id: int) -> list[Opportunity]:
        opportunities = self.db.query(Opportunity).filter(Opportunity.project_id == project_id).all()
        return sorted(
            opportunities,
            key=lambda o: (_CONFIDENCE_RANK.get(o.confidence, 99), -o.created_at.timestamp()),
        )

    def clear_opportunities(self, project_id: int) -> None:
        self.db.query(Opportunity).filter(Opportunity.project_id == project_id).delete()
        self.db.commit()

    # --- business profile -----------------------------------------------

    def create_business_profile(self, project_id: int, **fields) -> BusinessProfile:
        fields.setdefault("finding_ids", [])
        profile = BusinessProfile(project_id=project_id, **fields)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_latest_business_profile(self, project_id: int) -> BusinessProfile | None:
        return (
            self.db.query(BusinessProfile)
            .filter(BusinessProfile.project_id == project_id)
            .order_by(BusinessProfile.created_at.desc())
            .first()
        )

    # --- deep analysis runs -----------------------------------------------

    def create_deep_analysis_run(self, project_id: int) -> DeepAnalysisRun:
        run = DeepAnalysisRun(project_id=project_id, status="RUNNING")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete_deep_analysis_run(self, run_id: int, executive_summary: dict, quality_issues: list[dict]) -> DeepAnalysisRun | None:
        run = self.db.get(DeepAnalysisRun, run_id)
        if run is None:
            return None
        run.status = "COMPLETED"
        run.executive_summary = executive_summary
        run.quality_issues = quality_issues
        run.completed_at = _utcnow()
        self.db.commit()
        self.db.refresh(run)
        return run

    def fail_deep_analysis_run(self, run_id: int, error: str) -> DeepAnalysisRun | None:
        run = self.db.get(DeepAnalysisRun, run_id)
        if run is None:
            return None
        run.status = "FAILED"
        run.error = error
        run.completed_at = _utcnow()
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_deep_analysis_run(self, run_id: int) -> DeepAnalysisRun | None:
        return self.db.get(DeepAnalysisRun, run_id)

    def list_deep_analysis_runs(self, project_id: int) -> list[DeepAnalysisRun]:
        return (
            self.db.query(DeepAnalysisRun)
            .filter(DeepAnalysisRun.project_id == project_id)
            .order_by(DeepAnalysisRun.created_at.desc())
            .all()
        )

    # --- monitoring ---------------------------------------------------

    def create_monitoring_event(self, project_id: int, **fields) -> MonitoringEvent:
        event = MonitoringEvent(project_id=project_id, **fields)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_monitoring_events(self, project_id: int) -> list[MonitoringEvent]:
        return (
            self.db.query(MonitoringEvent)
            .filter(MonitoringEvent.project_id == project_id)
            .order_by(MonitoringEvent.created_at.desc())
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
