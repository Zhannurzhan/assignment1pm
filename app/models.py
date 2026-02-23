from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20)) # doctor/patient/admin

    # back_populates ensures that if you update a user, the patient/doctor link updates too
    patient: Mapped[Optional["Patient"]] = relationship(back_populates="user", uselist=False)
    doctor: Mapped[Optional["Doctor"]] = relationship(back_populates="user", uselist=False)

class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longtitude: Mapped[float] = mapped_column(Float, nullable=False)
    h3_index: Mapped[str] = mapped_column(String(20), nullable=False)
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    
    user: Mapped["User"] = relationship(back_populates="patient")
    appointments: Mapped[List["Appointment"]] = relationship(back_populates="patient")

class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    specialization: Mapped[str] = mapped_column(String(50), nullable=False) 

    user: Mapped["User"] = relationship(back_populates="doctor")
    appointments: Mapped[List["Appointment"]] = relationship(back_populates="doctor")

class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    h3_index: Mapped[str] = mapped_column(String(20), nullable=False)
    appointment_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")

class AuditLog(Base):
    __tablename__ = "audit_logs" 

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False) 
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )