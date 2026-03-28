
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime, timedelta, time
from app.modules.audit.router import Actions, log
from app.modules.auth.models import UserRole


from app.core.database import get_db
from app.core.dependencies import get_current_user, RoleChecker
from app.core.exceptions import NotFoundException, ConflictException, ValidationException
from app.core.h3_utils import gps_to_h3
from app.modules.auth.models import User
from app.modules.doctors.models import Doctor, DoctorSchedule, LicenseStatus, Specialty
from app.modules.appointments.models import Appointment
from app.modules.doctors.schemas import (
    DoctorProfileCreate,
    DoctorProfileUpdate,
    DoctorResponse,
    ScheduleSlotCreate,
    ScheduleSlotResponse,
    AvailableSlotsResponse,
    SpecialtyResponse,
)

router = APIRouter()

doctor_only = RoleChecker([UserRole.DOCTOR])


@router.get(
    "",
    response_model=list[DoctorResponse],
    summary="List all doctors (public)",
)
async def list_doctors(
    specialty_id: int | None = Query(default=None, description="Filter by specialty"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Doctor)
    if specialty_id:
        query = query.where(Doctor.specialty_id == specialty_id)
    result = await db.execute(query)
    return result.scalars().all()



@router.get(
    "/specialties",
    response_model=list[SpecialtyResponse],
    summary="List all specialties (public)",
)
async def list_specialties(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Specialty).order_by(Specialty.name))
    return result.scalars().all()



@router.post(
    "/profile",
    response_model=DoctorResponse,
    status_code=201,
    summary="Set up doctor profile",
)
async def setup_doctor_profile(
    dto: DoctorProfileCreate,
    current_user: User = Depends(doctor_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == current_user.id)
    )
    if result.scalar_one_or_none():
        raise ConflictException("Doctor profile already exists for this account")

    result = await db.execute(
        select(Doctor).where(Doctor.license_number == dto.license_number)
    )
    if result.scalar_one_or_none():
        raise ConflictException("A doctor with this license number already exists")

    result = await db.execute(
        select(Specialty).where(Specialty.id == dto.specialty_id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundException("Specialty not found")

    h3_index = gps_to_h3(dto.latitude, dto.longitude)

    doctor = Doctor(
        user_id=current_user.id,
        specialty_id=dto.specialty_id,
        license_number=dto.license_number,
        license_status=LicenseStatus.PENDING,
        years_of_experience=dto.years_of_experience,
        consultation_duration_minutes=dto.consultation_duration_minutes,
        bio=dto.bio,
        latitude=dto.latitude,
        longitude=dto.longitude,
        h3_index=h3_index,
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    await log(db, current_user.id, Actions.SETUP_DOCTOR_PROFILE, entity_type="Doctor", entity_id=doctor.id)
    return doctor



@router.get(
    "/me",
    response_model=DoctorResponse,
    summary="Get my doctor profile",
)
async def get_my_doctor_profile(
    current_user: User = Depends(doctor_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == current_user.id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Doctor profile not found. Please set it up first.")
    return doctor



@router.put(
    "/me",
    response_model=DoctorResponse,
    summary="Update my doctor profile",
)
async def update_my_doctor_profile(
    dto: DoctorProfileUpdate,
    current_user: User = Depends(doctor_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == current_user.id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Doctor profile not found.")

    if dto.specialty_id is not None:
        result = await db.execute(
            select(Specialty).where(Specialty.id == dto.specialty_id)
        )
        if not result.scalar_one_or_none():
            raise NotFoundException("Specialty not found")
        doctor.specialty_id = dto.specialty_id

    if dto.years_of_experience is not None:
        doctor.years_of_experience = dto.years_of_experience
    if dto.consultation_duration_minutes is not None:
        doctor.consultation_duration_minutes = dto.consultation_duration_minutes
    if dto.bio is not None:
        doctor.bio = dto.bio

    lat = dto.latitude if dto.latitude is not None else doctor.latitude
    lon = dto.longitude if dto.longitude is not None else doctor.longitude
    if dto.latitude is not None or dto.longitude is not None:
        doctor.latitude = lat
        doctor.longitude = lon
        doctor.h3_index = gps_to_h3(lat, lon)

    await db.commit()
    await db.refresh(doctor)
    return doctor



@router.post(
    "/schedule",
    response_model=list[ScheduleSlotResponse],
    summary="Set weekly availability",
    description="Send a list of slots. Each day_of_week is upserted — existing entries are updated.",
)
async def set_schedule(
    slots: list[ScheduleSlotCreate],
    current_user: User = Depends(doctor_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == current_user.id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Set up your doctor profile first.")

    saved = []
    for slot in slots:
        result = await db.execute(
            select(DoctorSchedule).where(
                DoctorSchedule.doctor_id == doctor.id,
                DoctorSchedule.day_of_week == slot.day_of_week,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.start_time = slot.start_time
            existing.end_time = slot.end_time
            existing.is_available = slot.is_available
            saved.append(existing)
        else:
            new_slot = DoctorSchedule(
                doctor_id=doctor.id,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                is_available=slot.is_available,
            )
            db.add(new_slot)
            saved.append(new_slot)

    await db.commit()
    for s in saved:
        await db.refresh(s)
    await log(db, current_user.id, Actions.SET_DOCTOR_SCHEDULE, entity_type="Doctor", entity_id=doctor.id)
    return saved



@router.get(
    "/schedule",
    response_model=list[ScheduleSlotResponse],
    summary="Get my weekly schedule",
)
async def get_my_schedule(
    current_user: User = Depends(doctor_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doctor).where(Doctor.user_id == current_user.id)
    )
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Doctor profile not found.")

    result = await db.execute(
        select(DoctorSchedule)
        .where(DoctorSchedule.doctor_id == doctor.id)
        .order_by(DoctorSchedule.day_of_week)
    )
    return result.scalars().all()



@router.get(
    "/{doctor_id}/available-slots",
    response_model=AvailableSlotsResponse,
    summary="Get available booking slots for a doctor on a date (public)",
)
async def get_available_slots(
    doctor_id: int,
    date: date = Query(..., description="Date to check, format: YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Doctor not found")

    day_of_week = date.weekday()
    result = await db.execute(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.day_of_week == day_of_week,
            DoctorSchedule.is_available == True,
        )
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        return AvailableSlotsResponse(
            doctor_id=doctor_id,
            date=date,
            available_slots=[],
        )

    # 3. Generate all candidate slots for this day
    #    e.g. 09:00, 09:30, 10:00 ... 16:30 for a 30-min consultation
    duration = doctor.consultation_duration_minutes
    slots = []
    current = datetime.combine(date, schedule.start_time)
    end_boundary = datetime.combine(date, schedule.end_time)

    while current + timedelta(minutes=duration) <= end_boundary:
        slots.append(current)
        current += timedelta(minutes=duration)

    if not slots:
        return AvailableSlotsResponse(
            doctor_id=doctor_id,
            date=date,
            available_slots=[],
        )

    day_start = datetime.combine(date, time(0, 0))
    day_end = datetime.combine(date, time(23, 59, 59))

    result = await db.execute(
        select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_time >= day_start,
            Appointment.appointment_time <= day_end,
            Appointment.status != "cancelled",
        )
    )
    booked = result.scalars().all()
    booked_times = {appt.appointment_time.replace(tzinfo=None) for appt in booked}

    available = [s for s in slots if s not in booked_times]

    return AvailableSlotsResponse(
        doctor_id=doctor_id,
        date=date,
        available_slots=available,
    )



@router.post(
    "/specialties",
    response_model=SpecialtyResponse,
    status_code=201,
    summary="Create a specialty (Admin only)",
)
async def create_specialty(
    name: str,
    current_user: User = Depends(RoleChecker(["ADMIN"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Specialty).where(Specialty.name == name))
    if result.scalar_one_or_none():
        raise ConflictException(f"Specialty '{name}' already exists")

    specialty = Specialty(name=name)
    db.add(specialty)
    await db.commit()
    await db.refresh(specialty)
    return specialty



@router.delete(
    "/specialties/{specialty_id}",
    status_code=204,
    summary="Delete a specialty (Admin only)",
)
async def delete_specialty(
    specialty_id: int,
    current_user: User = Depends(RoleChecker(["ADMIN"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Specialty).where(Specialty.id == specialty_id))
    specialty = result.scalar_one_or_none()
    if not specialty:
        raise NotFoundException("Specialty not found")

    await db.delete(specialty)
    await db.commit()



@router.put(
    "/specialties/{specialty_id}",
    response_model=SpecialtyResponse,
    summary="Rename a specialty (Admin only)",
)
async def update_specialty(
    specialty_id: int,
    name: str,
    current_user: User = Depends(RoleChecker(["ADMIN"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Specialty).where(Specialty.id == specialty_id))
    specialty = result.scalar_one_or_none()
    if not specialty:
        raise NotFoundException("Specialty not found")

    specialty.name = name
    await db.commit()
    await db.refresh(specialty)
    return specialty