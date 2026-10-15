from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    text: str
    link: Optional[str] = None
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    created_at: datetime
    read_at: Optional[datetime] = None


class UnreadCount(BaseModel):
    count: int


class PrefIn(BaseModel):
    kind: str
    enabled: bool
