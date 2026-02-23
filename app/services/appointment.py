from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Patient, Appointment
from app.services import h3_service, audit_service, event_service
from datetime import datetime

async def create_appointment(
    db: AsyncSession, 
    user_id: int, 
    doctor_id: int, 
    appt_time: datetime
):
    # 1. Get the Patient profile (to get their H3 location)
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalars().first()
    
    if not patient:
        raise Exception("Patient profile not found")

    # 2. Extract H3 index (Institutional Spatial Requirement)
    # The H3 index is already stored on the Patient profile from registration
    patient_h3 = patient.h3_index

    # 3. Create the Appointment
    new_appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor_id,
        appointment_time=appt_time,
        h3_index=patient_h3, # Storing spatial context for the appointment
        status="CONFIRMED"
    )
    db.add(new_appt)
    await db.flush() # Get the appointment ID before committing

    # 4. Trigger Audit Logging (Accountability)
    await audit_service.log_action(
        db=db,
        user_id=user_id,
        action="CREATE_APPOINTMENT",
        entity_type="Appointment",
        entity_id=new_appt.id
    )

    # 5. Trigger Event (Event-Driven Simulation)
    event_service.publish_event("appointment_created", {
        "appointment_id": new_appt.id,
        "patient_id": patient.id,
        "h3_region": patient_h3
    }, db)

    await db.commit()
    await db.refresh(new_appt)
    return new_appt