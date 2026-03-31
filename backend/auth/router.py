"""
Authentication router — /auth/login, /auth/logout, /auth/refresh, /auth/me
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import get_current_user
from auth.schemas import LoginRequest, TokenResponse, UserOut
from config import settings
from db.connection import get_db
from db.models import Session, User, UserAuditLog

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 30


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_access_token(user_id: str) -> tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expire


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Always run password check to prevent timing attacks
    dummy_hash = "$2b$12$dummy_hash_to_prevent_timing_attacks_xxxxx"
    candidate_hash = user.password_hash if user else dummy_hash

    if not user or not _verify_password(body.password, candidate_hash):
        if user:
            attempts = user.failed_login_attempts + 1
            update_data: dict = {"failed_login_attempts": attempts, "updated_at": datetime.now(timezone.utc)}
            if attempts >= MAX_LOGIN_ATTEMPTS:
                update_data["locked_until"] = datetime.now(timezone.utc) + timedelta(
                    minutes=LOCKOUT_MINUTES
                )
            await db.execute(update(User).where(User.id == user.id).values(**update_data))
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked until {user.locked_until.isoformat()}",
        )

    # Reset failed attempts on successful login
    token, expires_at = _create_access_token(str(user.id))

    session = Session(
        token=token,
        user_id=user.id,
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)

    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            failed_login_attempts=0,
            locked_until=None,
            last_login=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    log = UserAuditLog(
        actor_id=user.id,
        action="LOGIN",
        target_user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    await db.commit()

    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if token:
        result = await db.execute(select(Session).where(Session.token == token))
        session = result.scalar_one_or_none()
        if session:
            await db.delete(session)
            await db.commit()


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Invalidate old token
    auth_header = request.headers.get("authorization", "")
    old_token = auth_header.removeprefix("Bearer ").strip()
    if old_token:
        result = await db.execute(select(Session).where(Session.token == old_token))
        session = result.scalar_one_or_none()
        if session:
            await db.delete(session)

    token, expires_at = _create_access_token(str(current_user.id))
    new_session = Session(
        token=token,
        user_id=current_user.id,
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(new_session)
    await db.commit()

    return TokenResponse(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
