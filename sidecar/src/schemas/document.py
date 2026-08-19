from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    project_id: int
    filename: str
    file_type: str
    status: str
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
