
from fastapi import APIRouter, Depends,Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user, RoleChecker
from app.core.exceptions import NotFoundException, ConflictException
from app.core.h3_utils import gps_to_h3
from app.modules.audit.router import Actions, log
from app.modules.auth.models import User
from app.modules.patients.models import Patient
from app.modules.patients.schemas import (
    PatientProfileCreate,
    PatientProfileUpdate,
    PatientResponse,
)

router = APIRouter()

# Shortcut — reuse in all 3 endpoints
patient_only = RoleChecker(["PATIENT"])

# ── POST /patients/profile ────────────────────────────────────────────────────
@router.post(
    "/profile",
    response_model=PatientResponse,
    status_code=201,
    summary="Set up patient profile",
    description="Creates the patient profile for the logged-in user. Can only be called once.",
)
async def setup_patient_profile(
    dto: PatientProfileCreate,
    current_user: User = Depends(patient_only),
    db: AsyncSession = Depends(get_db),
):
    # Check: does a profile already exist for this user?
    result = await db.execute(
        select(Patient).where(Patient.user_id == current_user.id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictException("Patient profile already exists for this account")

    # Convert GPS → H3 cell index
    h3_index = gps_to_h3(dto.latitude, dto.longitude)

    # Create and save the patient profile

    patient = Patient(
        user_id=current_user.id,
        date_of_birth=dto.date_of_birth,
        phone=dto.phone,
        address=dto.address,
        blood_type=dto.blood_type,
        emergency_contact_name=dto.emergency_contact_name,
        emergency_contact_phone=dto.emergency_contact_phone,
        latitude=dto.latitude,
        longitude=dto.longitude,
        h3_index=h3_index,
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    await log(
        db=db,
        user_id=current_user.id,
        action=Actions.SETUP_PATIENT_PROFILE,
        entity_type="Patient",
        entity_id=patient.id,
)

    return patient

# ── GET /patients/me ──────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=PatientResponse,
    summary="Get my patient profile",
)
async def get_my_patient_profile(
    current_user: User = Depends(patient_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise NotFoundException("Patient profile not found. Please set it up first.")
    return patient

# ── PUT /patients/me ──────────────────────────────────────────────────────────
@router.put(
    "/me",
    response_model=PatientResponse,
    summary="Update my patient profile",
)
async def update_my_patient_profile(
    dto: PatientProfileUpdate,
    current_user: User = Depends(patient_only),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.user_id == current_user.id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise NotFoundException("Patient profile not found. Please set it up first.")

    # Only update fields that were actually sent
    if dto.phone is not None:
        patient.phone = dto.phone
    if dto.address is not None:
        patient.address = dto.address
    if dto.blood_type is not None:
        patient.blood_type = dto.blood_type
    if dto.emergency_contact_name is not None:
        patient.emergency_contact_name = dto.emergency_contact_name
    if dto.emergency_contact_phone is not None:
        patient.emergency_contact_phone = dto.emergency_contact_phone

    # If GPS changed — recalculate h3_index
    lat = dto.latitude if dto.latitude is not None else patient.latitude
    lon = dto.longitude if dto.longitude is not None else patient.longitude
    if dto.latitude is not None or dto.longitude is not None:
        patient.latitude = lat
        patient.longitude = lon
        patient.h3_index = gps_to_h3(lat, lon)

    await db.commit()
    await db.refresh(patient)
    await log(
        db=db,
        user_id=current_user.id,
        action=Actions.UPDATE_PATIENT_PROFILE,
        entity_type="Patient",
        entity_id=patient.id,
    )
    return patient