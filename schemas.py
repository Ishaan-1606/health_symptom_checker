from pydantic import BaseModel
from typing import Optional

class SymptomCheckRequest(BaseModel):
    symptoms: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class User(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True