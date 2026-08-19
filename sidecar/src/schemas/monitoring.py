from datetime import datetime

from pydantic import BaseModel


class MonitoringEventOut(BaseModel):
    id: int
    project_id: int
    entity_type: str
    event_type: str
    title: str
    previous_value: str | None
    new_value: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
