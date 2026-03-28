from pydantic import BaseModel, ConfigDict, field_validator
from datetime import date, datetime, time
from typing import Optional


class SpecialtyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class DoctorProfileCreate(BaseModel):
    specialty_id: int
    license_number: str
    years_of_experience: Optional[int] = None
    consultation_duration_minutes: int = 30
    bio: Optional[str] = None
    latitude: float
    longitude: float

    @field_validator("consultation_duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if not 15 <= v <= 120:
            raise ValueError("Consultation duration must be between 15 and 120 minutes")
        return v
    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v
class DoctorProfileUpdate(BaseModel):
    specialty_id: Optional[int] = None
    years_of_experience: Optional[int] = None
    consultation_duration_minutes: Optional[int] = None
    bio: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class DoctorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    specialty_id: int
    license_number: str
    license_status: str
    years_of_experience: Optional[int]
    consultation_duration_minutes: int
    bio: Optional[str]
    latitude: float
    longitude: float
    h3_index: str
    created_at: datetime
    updated_at: Optional[datetime]

class ScheduleSlotCreate(BaseModel):
    day_of_week: int   # 0 = Monday, 6 = Sunday
    start_time: time   # e.g. "09:00"
    end_time: time     # e.g. "17:00"
    is_available: bool = True

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("day_of_week must be 0 (Monday) to 6 (Sunday)")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_times(cls, v: time, info) -> time:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class ScheduleSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool


class AvailableSlotsResponse(BaseModel):
    doctor_id: int
    date: date
    available_slots: list[datetime] 