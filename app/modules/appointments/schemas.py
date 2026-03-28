from pydantic import BaseModel, field_validator, ConfigDict
from datetime import datetime, timezone
from typing import Optional



class AppointmentCreate(BaseModel):
    doctor_id: int
    appointment_time: datetime
    reason: Optional[str] = None

    @field_validator("appointment_time")
    @classmethod
    def validate_appointment_time(clc, value: datetime):
        if value.tzinfo is None:
            raise ValueError("appointment_time must be timezone-aware")
        
        now = datetime.now(timezone.utc)

        if value <= now:
            raise ValueError("Appointment time must be in the future")
        
        return value
    

    
class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_time: datetime
    duration_minutes: int
    status: str
    reason: Optional[str]
    notes: Optional[str]
    h3_index: Optional[str]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancelled_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CompleteRequest(BaseModel):
    notes: Optional[str] = None