# app/services/event_service.py

from typing import Callable, Dict, List
from sqlalchemy.orm import Session
from app.models import Appointment
from app.services.audit_service import log_action


# -------------------------------
# EVENT REGISTRY
# -------------------------------

# Dictionary that stores:
# { event_name: [list_of_handler_functions] }
event_handlers: Dict[str, List[Callable]] = {}


def register_event(event_name: str, handler: Callable):
    """
    Register a handler function for a specific event.
    """
    if event_name not in event_handlers:
        event_handlers[event_name] = []

    event_handlers[event_name].append(handler)


def publish_event(event_name: str, payload: dict, db: Session):
    """
    Trigger all handlers associated with an event.
    """
    handlers = event_handlers.get(event_name, [])

    for handler in handlers:
        handler(payload, db)


# -------------------------------
# EVENT HANDLERS
# -------------------------------

def handle_appointment_created(payload: dict, db: Session):
    """
    Triggered when appointment is created.
    """
    appointment_id = payload.get("appointment_id")
    patient_id = payload.get("patient_id")

    print(f"[EVENT] Appointment {appointment_id} created")

    # Simulate notification sending
    send_notification(patient_id, appointment_id)

    # Update region analytics
    update_region_statistics(db, appointment_id)


def send_notification(patient_id: int, appointment_id: int):
    """
    Simulated email/SMS notification.
    """
    print(
        f"[NOTIFICATION] Patient {patient_id} notified "
        f"about appointment {appointment_id}"
    )


def update_region_statistics(db, appointment_id: int):
    """
    Example analytics update logic (simulated).
    """
    print(f"[ANALYTICS] Updated region stats for appointment {appointment_id}")

# -------------------------------
# REGISTER EVENTS (IMPORTANT)
# -------------------------------

def init_event_system():
    """
    Call this once during app startup.
    """
    register_event("appointment_created", handle_appointment_created)