from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.database.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    name = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    projects = relationship(
        "Project",
        back_populates="company",
        cascade="all, delete-orphan",
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    company = relationship("Company", back_populates="projects")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="project", cascade="all, delete-orphan")
    hypotheses = relationship("Hypothesis", back_populates="project", cascade="all, delete-orphan")
    concerns = relationship("Concern", back_populates="project", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="project", cascade="all, delete-orphan")
    chat_messages = relationship(
        "ChatMessage",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class Document(Base):
    """A source file uploaded to a project. `status` tracks it through the
    ingest -> parse -> chunk -> index pipeline (spec section 6)."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    status = Column(String, nullable=False, default="INGESTED")
    error = Column(Text, nullable=True)

    project = relationship("Project", back_populates="documents")
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.order_index",
    )


class DocumentChunk(Base):
    """One retrievable, citable unit of a parsed document: a paragraph, a
    table row range, a spreadsheet range. `location` carries whatever
    page/sheet/row/column info the parser could recover, for citation."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    location = Column(JSON, nullable=True)

    document = relationship("Document", back_populates="chunks")


class Finding(Base):
    """The atomic evidence-typed unit (spec section 5): every conclusion the
    system states must be one of these, never bare prose. `source_type` is
    FACT | CALCULATION | INFERENCE | HYPOTHESIS | ASSUMPTION."""

    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    statement = Column(Text, nullable=False)
    source_type = Column(String, nullable=False)
    confidence = Column(String, nullable=False, default="UNKNOWN")

    # "llm" (QuickAnswerService) or "engine" (a deterministic analysis service,
    # e.g. FinancialAnalysisService) — lets prompts prefer engine-computed
    # numbers over asking the LLM to recompute them (see quick_answer_service).
    origin = Column(String, nullable=False, default="llm")

    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    location = Column(JSON, nullable=True)

    calculation = Column(Text, nullable=True)
    assumption = Column(Text, nullable=True)

    project = relationship("Project", back_populates="findings")


class Hypothesis(Base):
    """Spec section 4. Generation (a Hypothesis Manager agent proposing these
    from findings) is deferred to Phase 3's orchestration — this is the
    tracking data model: status, evidence links, what would move it forward."""

    __tablename__ = "hypotheses"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    statement = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="PLAUSIBLE")

    supporting_finding_ids = Column(JSON, nullable=True)
    contradicting_finding_ids = Column(JSON, nullable=True)
    data_required = Column(Text, nullable=True)
    business_impact = Column(Text, nullable=True)
    priority = Column(String, nullable=True)
    next_test = Column(Text, nullable=True)

    project = relationship("Project", back_populates="hypotheses")


class Concern(Base):
    """Spec section 4, Concern Detection. Persisted output of a detector —
    currently the deterministic rule-based one in
    services/concern_detection_service.py, run over FinancialAnalysisService's
    output."""

    __tablename__ = "concerns"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    evidence_finding_ids = Column(JSON, nullable=True)
    business_impact = Column(Text, nullable=True)
    root_cause_hypothesis_ids = Column(JSON, nullable=True)
    confidence = Column(String, nullable=False, default="UNKNOWN")
    what_would_change_conclusion = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)

    project = relationship("Project", back_populates="concerns")


class Opportunity(Base):
    """Spec section 4, Opportunity Detection — same status as Concern above."""

    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=False)
    evidence_finding_ids = Column(JSON, nullable=True)
    estimated_value = Column(Text, nullable=True)
    required_capabilities = Column(Text, nullable=True)
    risks = Column(Text, nullable=True)
    confidence = Column(String, nullable=False, default="UNKNOWN")
    next_step = Column(Text, nullable=True)

    project = relationship("Project", back_populates="opportunities")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    finding_ids = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="chat_messages")
