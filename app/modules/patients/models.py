'''
patients {
    int id PK
    int user_id FK
    date date_of_birth
    string phone
    string address
    string blood_type
    string emergency_contact_name
    string emergency_contact_phone
    float latitude
    float longitude
    string h3_index
    datetime created_at
    datetime updated_at
  }
'''
from sqlalchemy import Integer,ForeignKey,DateTime,String,Date,Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )
    date_of_birth: Mapped[Date] = mapped_column(Date, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    h3_index: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True  # indexed for fast GROUP BY in analytics
    )
    created_at: Mapped[DateTime] = mapped_column(
    DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True
    )
    appointments = relationship("Appointment", back_populates="patient")