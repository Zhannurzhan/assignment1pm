from sqlalchemy import (
    Boolean, String, Integer, ForeignKey,
    DateTime, Enum, Float, Text, Time, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime, time  
import enum

from app.core.database import Base



class LicenseStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"



class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    doctors = relationship("Doctor", back_populates="specialty")



class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    specialty_id: Mapped[int] = mapped_column(Integer, ForeignKey("specialties.id"), nullable=False)

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_of_experience: Mapped[int] = mapped_column(Integer, default=0)
    consultation_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    license_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    license_status: Mapped[LicenseStatus] = mapped_column(Enum(LicenseStatus), default=LicenseStatus.PENDING)
    license_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    h3_index: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())



    # user = relationship("User", back_populates="doctor")
    specialty = relationship("Specialty", back_populates="doctors")
    # appointments = relationship("Appointment", back_populates="doctor")



class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("doctors.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)   
    end_time: Mapped[time] = mapped_column(Time, nullable=False)    
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


    __table_args__ = (
        UniqueConstraint("doctor_id", "day_of_week", name="uq_doctor_day"),
    )