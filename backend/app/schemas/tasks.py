from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class TaskIn(BaseModel):
    title: str
    description: Optional[str] = None
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    duration_min: Optional[int] = None
    location: Optional[str] = None

class TaskOut(TaskIn):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
