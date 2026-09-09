from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    resource_type: str
    resource_id: int | None = None
    previous_hash: str | None = None
    integrity_hash: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)