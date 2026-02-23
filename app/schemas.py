from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    role: Literal["Patient", "Doctor", "Admin"] = "Patient"

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class AppointmentCreate(BaseModel):
    doctor_id: int
    datetime: datetime

class AppointmentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    doctor_id: int
    appointment_time: datetime
    status: str
    h3_index: str