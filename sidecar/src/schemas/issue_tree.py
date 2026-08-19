from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class IssueNodeDraft(BaseModel):
    """What the LLM is asked to produce for one branch (spec section 4).
    `is_forced_mece` + `overlap_note` are the explicit escape hatch: "do not
    force MECE structures where the underlying business reality does not
    support them" — most nodes should leave this false/null."""

    label: str
    is_forced_mece: bool = False
    overlap_note: str | None = None
    children: list[IssueNodeDraft] = []


class IssueTreeDraft(BaseModel):
    root_children: list[IssueNodeDraft]
    overall_note: str | None = None


class IssueNodeOut(BaseModel):
    id: int
    label: str
    is_forced_mece: bool
    overlap_note: str | None
    children: list[IssueNodeOut] = []


class IssueTreeOut(BaseModel):
    id: int
    project_id: int
    question: str
    overall_note: str | None
    root_children: list[IssueNodeOut]
    created_at: datetime

    model_config = {"from_attributes": True}


class IssueTreeRequest(BaseModel):
    question: str
    use_claude: bool = False  # explicit opt-in; see llm/router.py — local Ollama is the default
