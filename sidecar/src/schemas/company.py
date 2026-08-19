from datetime import datetime

from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    industry: str | None = None
    notes: str | None = None


class CompanyOut(BaseModel):
    id: int
    name: str
    industry: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
