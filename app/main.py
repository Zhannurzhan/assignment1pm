from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import Base, engine, get_db
from app.auth import get_current_user, RoleChecker
from app.models import Patient, User, Appointment, AuditLog
from app.schemas import UserCreate, AppointmentCreate, AppointmentResponse, TokenResponse
from app.auth import hash_password, verify_password, create_access_token
from app.services.appointment import create_appointment as create_appointment_service
from app.services.audit_service import log_action
from app.services.event_service import init_event_system
from app.services.h3_service import aggregate_by_h3

try:
    from swagger_ui_bundle import swagger_ui_3_path
except Exception:
    swagger_ui_3_path = None

app = FastAPI(docs_url=None, redoc_url=None)

if swagger_ui_3_path:
    app.mount("/swagger-ui", StaticFiles(directory=swagger_ui_3_path), name="swagger-ui")


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html():
    if swagger_ui_3_path:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            swagger_js_url="/swagger-ui/swagger-ui-bundle.js",
            swagger_css_url="/swagger-ui/swagger-ui.css",
            swagger_favicon_url="/swagger-ui/favicon-32x32.png",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        )

    # Fallback to CDN (original FastAPI behavior)
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )


@app.on_event("startup")
async def create_db_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    init_event_system()


@app.post("/register")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):

    result_email = await db.execute(
        select(User).where(User.email == user.email)
    )
    existing_email = result_email.scalars().first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    result_username = await db.execute(
        select(User).where(User.username == user.username)
    )
    existing_username = result_username.scalars().first()

    if existing_username:
        raise HTTPException(
            status_code=400,
            detail="Username already taken"
        )

    hashed_password = hash_password(user.password)

    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {"message": "User registered successfully"}

@app.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    email = form_data.username
    password = form_data.password

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id)})

    await log_action(         
        db=db,
        user_id=user.id,
        action="Login",
        entity_type="User",
        entity_id=user.id
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@app.post("/setup-patient")
async def setup_patient(
    latitude: float,
    longitude: float, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Patient"]))
):
    import h3
    h3_index = h3.latlng_to_cell(latitude, longitude, 7)
    
    patient = Patient(
        user_id=current_user.id,
        latitude=latitude,
        longtitude=longitude,  
        h3_index=h3_index
    )
    db.add(patient)
    await db.commit()
    return {"message": "Patient profile created", "h3_index": h3_index}


@app.post("/appointments", response_model=AppointmentResponse)
async def create_appointment_endpoint(
    appointment_data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Patient"]))
):
    appointment = await create_appointment_service(
        db=db,
        user_id=current_user.id,        
        doctor_id=appointment_data.doctor_id,
        appt_time=appointment_data.datetime 
    )
    return appointment

@app.get("/appointments/my", response_model=List[AppointmentResponse])
async def get_my_appointments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "Patient":
        from app.models import Patient as PatientModel
        patient_result = await db.execute(
            select(PatientModel).where(PatientModel.user_id == current_user.id)
        )
        patient = patient_result.scalars().first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        result = await db.execute(
            select(Appointment).where(
                Appointment.patient_id == patient.id
            )
        )

    elif current_user.role == "Doctor":
        from app.models import Doctor as DoctorModel
        doctor_result = await db.execute(
            select(DoctorModel).where(DoctorModel.user_id == current_user.id)
        )
        doctor = doctor_result.scalars().first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor profile not found")
        result = await db.execute(
            select(Appointment).where(
                Appointment.doctor_id == doctor.id
            )
        )

    else:
        raise HTTPException(status_code=403, detail="Access denied")

    appointments = result.scalars().all()
    return appointments
    
@app.get("/analytics/{h3_index}")
async def get_region_analytics(
    h3_index: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Admin"]))
):
    result = await aggregate_by_h3(db, h3_index)

    return {
        "region": h3_index,
        "appointments": result
    }

@app.get("/audit-logs")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["Admin"]))
):
    result = await db.execute(select(AuditLog))
    logs = result.scalars().all()

    return logs

@app.get("/")
def root():
    return {"message" : "Clinical management system running"}