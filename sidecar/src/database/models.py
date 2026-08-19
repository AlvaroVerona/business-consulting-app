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

    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    location = Column(JSON, nullable=True)

    calculation = Column(Text, nullable=True)
    assumption = Column(Text, nullable=True)

    project = relationship("Project", back_populates="findings")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    finding_ids = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="chat_messages")
