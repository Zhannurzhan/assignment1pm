from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog
async def log_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int = None
):
    """
    Records every critical system action
    """
    new_log = AuditLog(
        user_id = user_id,
        action=action,
        entity_type = entity_type,
        entity_id = entity_id
    )
    db.add(new_log)
    await db.commit()
    print(f"Audit log: User {user_id} performed {action} on {entity_type} {entity_id}")
    