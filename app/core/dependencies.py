from typing import Annotated
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import is_token_blacklisted
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.modules.auth.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")



async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)],db: AsyncSession = Depends(get_db)):

    payload = decode_access_token(token)

    if not payload or "user_id" not in payload:
        raise UnauthorizedException("Invalid or expired token")
    
    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise UnauthorizedException("Token has been revoked. Please log in again.")

    user = await db.get(User, payload["user_id"])

    if not user:
        raise UnauthorizedException("User not found")
    
    if not user.is_active:
        raise UnauthorizedException("Account is deactivated")

    return user



async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    
    if not current_user.is_active:
        raise UnauthorizedException("Inactive user")
    return current_user


class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise ForbiddenException("Not enough permissions")
        return user