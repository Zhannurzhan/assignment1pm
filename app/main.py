from contextlib import asynccontextmanager
import traceback
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.modules.auth.router import router as auth_router
from app.core.event_bus import setup as setup_events

from app.modules.patients.router import router as patients_router   # NEW today
from app.modules.doctors.router import router as doctors_router     # NEW today
from app.modules.appointments.router import router as appointments_router
from app.modules.analytics.router import router as analytics_router
from app.modules.audit.router import router as audit_router

from app.core.database import init_db
from app.core.event_bus import setup

# ── Import all models BEFORE init_db() ───────────────────────────────────────
# These imports register each model on Base.metadata so SQLAlchemy
# knows to create the table. If you forget one, that table won't exist.
from app.modules.auth.models import User                          # noqa: F401
from app.modules.patients.models import Patient                   # noqa: F401
from app.modules.doctors.models import Doctor, DoctorSchedule, Specialty   # noqa: F401
from app.modules.appointments.models import Appointment           # noqa: F401
from app.modules.audit.models import AuditLog            
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: runs once when the server starts
    print("Starting up...")
    await init_db()      
        # creates all tables in clinic.db
    print("Database ready. All tables created.")
    # event_bus.setup() will be added here on Day 4
    setup_events()
    yield
    # SHUTDOWN: runs once when the server stops
    print("Shutting down.")


# ── Create the FastAPI app ────────────────────────────────────────────────────
app = FastAPI(
    title="Clinic Management System",
    version="1.0.0",
    description="Backend API for patients, doctors, and appointments",
    lifespan=lifespan,
)

# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Returns 422 with human-readable field errors instead of raw Pydantic output."""
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"]})
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Returns 500 without exposing SQL details to the client."""
    print(f"[DB ERROR] {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred. Please try again."},
    )
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catches any unhandled exception and returns 500."""
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )

# ── CORS middleware ───────────────────────────────────────────────────────────
# Allows your frontend (React, Flutter, Postman) to call this API.
# allow_origins=["*"] is fine for development.
# In production change "*" to your actual frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    setup()
    print("Event bus ready")

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(patients_router, prefix="/patients", tags=["patients"])
app.include_router(doctors_router, prefix="/doctors", tags=["doctors"])
app.include_router(appointments_router, prefix="/appointments", tags=["appointments"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
app.include_router(audit_router, prefix="/admin", tags=["audit"])

# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["health"])
async def health_check():
    return {"status": "ok", "message": "Clinic API is running"}
