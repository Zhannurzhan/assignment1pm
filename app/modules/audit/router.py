from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.pagination import paginate
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditLogResponse


router = APIRouter()

class Actions:
    REGISTER = "REGISTER"
    LOGIN = "LOGIN"
    SETUP_PATIENT_PROFILE = "SETUP_PATIENT_PROFILE"
    UPDATE_PATIENT_PROFILE = "SETUP_PATIENT_PROFILE"
    SETUP_DOCTOR_PROFILE = "SETUP_PATIENT_PROFILE"
    SET_DOCTOR_SCHEDULE = "SET_DOCTOR_SCHEDULE"
    BOOK_APPOINTMENT = "BOOK_APPOINTMENT"
    CANCEL_APPOINTMENT = "CANCEL_APPOINTMENT"
    COMPLETE_APPOINTMENT = "COMPLETE_APPOINTMENT"
    DEACTIVATE_USER = "DEACTIVATE_USER"
    ACTIVATE_USER = "ACTIVATE_USER"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"
    VIEW_ANALYTICS = "VIEW_ANALYTICS"



async def log(
    db: AsyncSession,
    user_id: int,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    extra_data: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    ip = None
    user_agent = None
    if request:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    entry = AuditLog(
        user_id = user_id,
        action = action,
        entity_type = entity_type,
        entity_id = entity_id,
        extra_data = extra_data,
        ip_address = ip,
        user_agent = user_agent,
    )
    db.add(entry)
    await db.commit()



@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(AuditLog)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    if action:
        query = query.where(AuditLog.action == action)

    if start_date:
        query = query.where(AuditLog.created_at >= start_date)

    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
    
    query = query.order_by(desc(AuditLog.created_at))

    result = await paginate(query, page, page_size, db)
    
    result.items = [AuditLogResponse.model_validate(a) for a in result.items]

    await log(db = db, user_id = current_user.id, action = Actions.VIEW_AUDIT_LOGS)
    return result