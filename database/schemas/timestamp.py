from pydantic import BaseModel
from typing import Optional

class TimestampBase(BaseModel):
    cnic: str
    timestamp: float
    cam_id: int

class TimestampCreate(TimestampBase):
    pass

class Timestamp(TimestampBase):
    class Config:
        from_attributes = True
        orm_mode = True
