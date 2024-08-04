from pydantic import BaseModel
from typing import Optional

class NumberPlateTimestampBase(BaseModel):
    number_plate: str
    plate_confidence: float
    timestamp: str
    all_details: str
    img_path: str
    cam_id: int

class NumberPlateTimestampCreate(NumberPlateTimestampBase):
    pass

class NumberPlateTimestamp(NumberPlateTimestampBase):
    class Config:
        from_attributes = True
        orm_mode = True