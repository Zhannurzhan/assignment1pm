from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import RoleChecker, get_current_user, oauth2_scheme
from app.core.exceptions import ConflictException
from app.core.pagination import paginate
from app.core.security import decode_access_token, hash_password
from app.core.cache import blacklist_token
from app.modules.auth.schemas import RegisterSchema, LoginSchema, TokenResponse, UserResponse
from app.modules.auth.service import AuthService
from app.modules.auth.models import User, UserRole
from app.modules.audit.router import log, Actions

router = APIRouter(tags=["Auth"])



def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)



@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    dto: RegisterSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    result = await auth_service.register(dto)

    await log(
        db=db,
        user_id=result["user_id"],     
        action=Actions.REGISTER,
        entity_type="User",
        entity_id=result["user_id"],   
        request=request,
    )

    return result



@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),  
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    result = await auth_service.login(form_data.username, form_data.password)
    await log(
        db=db,
        user_id=result["user_id"],
        action=Actions.LOGIN,
        entity_type="User",
        entity_id=result["user_id"],
        request=request,
    )
    return result



@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.me(current_user)




@router.post("/logout", summary="Logout — revoke current token")
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")

    if jti and exp:
        remaining = int(exp - datetime.utcnow().timestamp())
        if remaining > 0:
            await blacklist_token(jti, remaining)

    await log(db=db, user_id=current_user.id, action="LOGOUT",
              entity_type="User", entity_id=current_user.id)

    return {"message": "Logged out successfully"}





@router.post(
    "/admin/users/create-doctor",
    response_model=UserResponse,
    status_code=201,
    summary="Create a doctor account (Admin only)",
    dependencies=[Depends(RoleChecker(["ADMIN"]))],
)
async def create_doctor_account(
    dto: RegisterSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check email unique
    result = await db.execute(select(User).where(User.email == dto.email))
    if result.scalar_one_or_none():
        raise ConflictException("Email already registered")

    # Check username unique
    result = await db.execute(select(User).where(User.username == dto.username))
    if result.scalar_one_or_none():
        raise ConflictException("Username already taken")

    user = User(
        username=dto.username,
        email=dto.email,
        password_hash=hash_password(dto.password),
        role="DOCTOR",      # ← hardcoded
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log(
        db=db,
        user_id=current_user.id,
        action=Actions.REGISTER,
        entity_type="User",
        entity_id=user.id,
        extra_data={"created_role": "DOCTOR", "created_by": current_user.id},
        request=request,
    )

    return UserResponse.model_validate(user)



@router.post(
    "/admin/users/create-admin",
    response_model=UserResponse,
    status_code=201,
    summary="Create an admin account (Admin only)",
    dependencies=[Depends(RoleChecker(["ADMIN"]))],
)
async def create_admin_account(
    dto: RegisterSchema,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.email == dto.email))
    if result.scalar_one_or_none():
        raise ConflictException("Email already registered")

    result = await db.execute(select(User).where(User.username == dto.username))
    if result.scalar_one_or_none():
        raise ConflictException("Username already taken")

    user = User(
        username=dto.username,
        email=dto.email,
        password_hash=hash_password(dto.password),
        role="ADMIN",       # ← hardcoded
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log(
        db=db,
        user_id=current_user.id,
        action=Actions.REGISTER,
        entity_type="User",
        entity_id=user.id,
        extra_data={"created_role": "ADMIN", "created_by": current_user.id},
        request=request,
    )

    return UserResponse.model_validate(user)



@router.get("/admin/users", dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=100),
    role: UserRole | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(User).order_by(User.created_at.desc())
    if role:
        query = query.where(User.role == role)
    if search:
        query = query.where(
            or_(User.username.ilike(f"%{search}%"), User.email.ilike(f"%{search}%"))
        )

    paged = await paginate(query, page, page_size, db)

    paged.items = [UserResponse.model_validate(u) for u in paged.items]
    return paged



@router.get("/admin/users/{user_id}", response_model=UserResponse,dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def get_user_by_id(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user



@router.put("/admin/users/{user_id}/deactivate",dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def deactivate_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    await log(db=db, user_id=current_user.id, action=Actions.DEACTIVATE_USER,
              entity_type="User", entity_id=user.id)
    return {"message": "User deactivated"}



@router.put("/admin/users/{user_id}/activate",dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def activate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    await log(db=db, user_id=current_user.id, action=Actions.ACTIVATE_USER,
              entity_type="User", entity_id=user.id)
    return {"message": "User activated"}