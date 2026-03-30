"""
JWT validation middleware + role-based access control helpers.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.connection import get_db
from db.models import User

bearer_scheme = HTTPBearer(auto_error=False)

PERMISSIONS: dict[str, list[str]] = {
    "super_admin": ["*"],
    "admin": [
        "view_dashboard", "view_signals", "view_trades", "view_predictions",
        "view_bot_feed", "view_self_heal", "view_reports", "view_admin",
        "manage_users", "configure_bot", "approve_heal", "restart_services",
    ],
    "analyst": [
        "view_dashboard", "view_signals", "view_trades", "view_predictions",
        "view_bot_feed", "view_reports",
        "enter_manual_trade", "exit_trade", "set_capital",
    ],
    "viewer": ["view_dashboard"],
}


def _decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account temporarily locked")

    return user


def has_permission(user: User, permission: str) -> bool:
    perms = PERMISSIONS.get(user.role, [])
    return "*" in perms or permission in perms


def require_permission(permission: str):
    """Returns a FastAPI dependency that checks a specific permission."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return current_user
    return _check


def require_roles(*roles: str):
    """Returns a FastAPI dependency that checks the user is one of the given roles."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return current_user
    return _check


# Convenience aliases
RequireAdmin = require_roles("super_admin", "admin")
RequireAnalyst = require_roles("super_admin", "admin", "analyst")
RequireSuperAdmin = require_roles("super_admin")
