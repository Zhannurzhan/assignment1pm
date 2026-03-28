from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from datetime import datetime, timedelta, date, time
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.database import get_db
from app.core.dependencies import get_current_user, RoleChecker
from app.core.exceptions import (
    NotFoundException, ConflictException,
    ValidationException, ForbiddenException,
)
from app.core import event_bus
from app.core.pagination import paginate
from app.modules.audit.router import Actions, log
from app.modules.auth.models import User
from app.modules.patients.models import Patient
from app.modules.doctors.models import Doctor, DoctorSchedule
from app.modules.appointments.models import Appointment, AppointmentStatus
from app.modules.appointments.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    CompleteRequest,
)

router = APIRouter()



async def check_doctor_conflict(
    doctor_id: int,
    start: datetime,
    duration_minutes: int,
    db: AsyncSession,
) -> bool:
    end = start + timedelta(minutes=duration_minutes)
    result = await db.execute(
        select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
        )
    )
    return result.scalar_one_or_none() is not None



async def check_patient_conflict(
    patient_id: int,
    start: datetime,
    duration_minutes: int,
    db: AsyncSession,
) -> bool:
    end = start + timedelta(minutes=duration_minutes)
    result = await db.execute(
        select(Appointment).where(
            Appointment.patient_id == patient_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.appointment_time >= start,
            Appointment.appointment_time < end,
        )
    )
    return result.scalar_one_or_none() is not None



@router.post("", response_model=AppointmentResponse, status_code=201, summary="Book an appointment")
async def book_appointment(
    dto: AppointmentCreate,
    current_user: User = Depends(RoleChecker(["PATIENT"])),
    db: AsyncSession = Depends(get_db),
):
    # 1. Get patient profile
    result = await db.execute(
        select(Patient).where(Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise NotFoundException("Set up your patient profile first")

    # 2. Get doctor
    result = await db.execute(
        select(Doctor).where(Doctor.id == dto.doctor_id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Doctor not found")

    # 3. Normalise appointment_time to naive UTC for DB comparison
    appt_time = dto.appointment_time
    if appt_time.tzinfo is not None:
        appt_time = appt_time.replace(tzinfo=None)

    # 4. Check doctor has a schedule for this day
    day_of_week = appt_time.weekday()
    result = await db.execute(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor.id,
            DoctorSchedule.day_of_week == day_of_week,
            DoctorSchedule.is_available == True,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise ValidationException("Doctor is not available on this day")

    # 5. Check time is within working hours
    appt_time_only = appt_time.time()
    if not (schedule.start_time <= appt_time_only < schedule.end_time):
        raise ValidationException(
            f"Outside doctor's working hours ({schedule.start_time}–{schedule.end_time})"
        )

    # 6. Check doctor conflict
    if await check_doctor_conflict(doctor.id, appt_time, doctor.consultation_duration_minutes, db):
        raise ConflictException("Doctor is already booked at this time")

    # 7. Check patient conflict
    if await check_patient_conflict(patient.id, appt_time, doctor.consultation_duration_minutes, db):
        raise ConflictException("You already have an appointment at this time")

    # 8. Create appointment
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_time=appt_time,
        duration_minutes=doctor.consultation_duration_minutes,
        status=AppointmentStatus.SCHEDULED,
        reason=dto.reason,
        h3_index=patient.h3_index,
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    await log(db, current_user.id, Actions.BOOK_APPOINTMENT,
              entity_type="Appointment", entity_id=appointment.id,
              extra_data={"doctor_id": doctor.id, "time": str(appt_time)})

    # Publish event — handlers print to terminal
    await event_bus.publish("appointment_created", {
        "appointment_id": appointment.id,
        "patient_id": patient.id,
        "doctor_id": doctor.id,
        "h3_index": appointment.h3_index,
    })

    return appointment



@router.get("/my", response_model=list[AppointmentResponse], summary="Get my appointments (Patient or Doctor)")
async def get_my_appointments(
    status: Optional[str] = Query(default=None, description="Filter: scheduled/completed/cancelled"),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    current_user: User = Depends(RoleChecker(["PATIENT", "DOCTOR"])),
    db: AsyncSession = Depends(get_db),
):
    # Build base query depending on role
    if current_user.role == "PATIENT":
        result = await db.execute(
            select(Patient).where(Patient.user_id == current_user.id)
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise NotFoundException("Patient profile not found")
        query = select(Appointment).where(Appointment.patient_id == patient.id)

    else:  # DOCTOR
        result = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id)
        )
        doctor = result.scalar_one_or_none()
        if not doctor:
            raise NotFoundException("Doctor profile not found")
        query = select(Appointment).where(Appointment.doctor_id == doctor.id)

    # Apply optional filters
    if status:
        query = query.where(Appointment.status == status)
    if from_date:
        query = query.where(
            Appointment.appointment_time >= datetime.combine(from_date, time.min)
        )
    if to_date:
        query = query.where(
            Appointment.appointment_time <= datetime.combine(to_date, time.max)
        )

    query = query.order_by(Appointment.appointment_time)
    result = await db.execute(query)
    return result.scalars().all()



@router.put(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment (Patient or Doctor)",
)
async def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(RoleChecker(["PATIENT", "DOCTOR"])),
    db: AsyncSession = Depends(get_db),
):
    # Fetch appointment
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise NotFoundException("Appointment not found")

    # Verify ownership
    if current_user.role == "PATIENT":
        result = await db.execute(
            select(Patient).where(Patient.user_id == current_user.id)
        )
        patient = result.scalar_one_or_none()
        if not patient or appointment.patient_id != patient.id:
            raise ForbiddenException("This is not your appointment")

    elif current_user.role == "DOCTOR":
        result = await db.execute(
            select(Doctor).where(Doctor.user_id == current_user.id)
        )
        doctor = result.scalar_one_or_none()
        if not doctor or appointment.doctor_id != doctor.id:
            raise ForbiddenException("This is not your appointment")

    # Check it can be cancelled
    if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED):
        raise ValidationException(f"Appointment is already {appointment.status}")

    # Check it's in the future
    if appointment.appointment_time <= datetime.utcnow():
        raise ValidationException("Cannot cancel a past appointment")

    # Cancel
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = datetime.utcnow()
    appointment.cancelled_by = current_user.id
    await db.commit()
    await db.refresh(appointment)
    await log(db, current_user.id, Actions.CANCEL_APPOINTMENT, entity_type="Appointment", entity_id=appointment.id)

    await event_bus.publish("appointment_cancelled", {
        "appointment_id": appointment.id,
        "cancelled_by": current_user.id,
    })

    return appointment



@router.put(
    "/{appointment_id}/complete",
    response_model=AppointmentResponse,
    summary="Mark appointment as completed (Doctor only)",
)
async def complete_appointment(
    appointment_id: int,
    dto: CompleteRequest,
    current_user: User = Depends(RoleChecker(["DOCTOR"])),
    db: AsyncSession = Depends(get_db),
):
    # Fetch appointment
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise NotFoundException("Appointment not found")

    # Verify this doctor owns it
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == current_user.id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor or appointment.doctor_id != doctor.id:
        raise ForbiddenException("This is not your appointment")

    # Must be scheduled
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise ValidationException(
            f"Only scheduled appointments can be completed. Current status: {appointment.status}"
        )

    # Complete
    appointment.status = AppointmentStatus.COMPLETED
    appointment.completed_at = datetime.utcnow()
    if dto.notes:
        appointment.notes = dto.notes

    await db.commit()
    await db.refresh(appointment)
    await log(db, current_user.id, Actions.COMPLETE_APPOINTMENT, entity_type="Appointment", entity_id=appointment.id)
    return appointment



@router.get("/admin/all", dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def get_all_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=100),
    status: AppointmentStatus | None = None,
    doctor_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Appointment)

    if status:
        query.where(Appointment.status == status)

    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)

    if start_date and end_date:
        query = query.where(
            and_(
                Appointment.appointment_time >= start_date,
                Appointment.appointment_time <= end_date,
            )
        )

    return await paginate(query, page, page_size, db)



@router.put("/{appointment_id}/admin-cancel", dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def admin_cancel_appointment(
    appointment_id: int,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Already cancelled")
    
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = datetime.utcnow()
    appointment.cancelled_by = current_user.id

    if reason:
        appointment.notes = reason
    
    await db.commit()
    await db.refresh(appointment)
    await log(db, current_user.id, Actions.CANCEL_APPOINTMENT, entity_type="Appointment", entity_id=appointment.id)

    await event_bus.publish("appointment.cancelled", appointment_id=appointment_id)

    return {"message": "Appointment cancelled by admin"}

