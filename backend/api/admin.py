"""
Admin API endpoints — user management, signal rules, audit log.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import RequireAdmin, RequireSuperAdmin, get_current_user
from auth.schemas import CreateUserRequest, UpdateUserRequest
from db.connection import get_db
from db.models import SignalRule, User, UserAuditLog

router = APIRouter(prefix="/api/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/users")
async def list_users(
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return {"users": users}


@router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    # Admins can only create analyst/viewer, not other admins
    if current_user.role == "admin" and body.role not in ("analyst", "viewer"):
        raise HTTPException(status_code=403, detail="Admins can only create analyst or viewer accounts")

    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        email=body.email,
        password_hash=pwd_context.hash(body.password),
        name=body.name,
        role=body.role,
        added_by=current_user.id,
        capital=body.capital,
        telegram_chat_id=body.telegram_chat_id,
    )
    db.add(new_user)

    log = UserAuditLog(
        actor_id=current_user.id,
        action="USER_CREATED",
        target_user_id=new_user.id,
        details={"role": body.role, "email": body.email},
    )
    db.add(log)
    await db.commit()
    await db.refresh(new_user)
    return {"user": new_user}


@router.put("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Admins cannot modify other admins or super_admins
    if current_user.role == "admin" and target.role in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Cannot modify admin or super_admin accounts")

    changes: dict = {}
    if body.role is not None:
        changes["role"] = body.role
        target.role = body.role
    if body.is_active is not None:
        changes["is_active"] = body.is_active
        target.is_active = body.is_active
    if body.capital is not None:
        changes["capital"] = body.capital
        target.capital = body.capital
    if body.trade_mode is not None:
        changes["trade_mode"] = body.trade_mode
        target.trade_mode = body.trade_mode
    if body.telegram_chat_id is not None:
        changes["telegram_chat_id"] = body.telegram_chat_id
        target.telegram_chat_id = body.telegram_chat_id

    target.updated_at = datetime.now(timezone.utc)

    log = UserAuditLog(
        actor_id=current_user.id,
        action="USER_UPDATED",
        target_user_id=user_id,
        details=changes,
    )
    db.add(log)
    await db.commit()
    await db.refresh(target)
    return {"user": target}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(RequireSuperAdmin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    log = UserAuditLog(
        actor_id=current_user.id,
        action="USER_DELETED",
        target_user_id=user_id,
        details={"email": target.email},
    )
    db.add(log)
    await db.delete(target)
    await db.commit()


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAuditLog).order_by(UserAuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return {"logs": logs}


@router.get("/signal-rules")
async def get_signal_rules(
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SignalRule).where(SignalRule.is_active == True).order_by(SignalRule.rule_name)
    )
    rules = result.scalars().all()
    return {"rules": rules}


class UpdateRuleRequest:
    pass


from pydantic import BaseModel
from typing import Any


class UpdateSignalRuleRequest(BaseModel):
    rule_name: str
    value: Any
    reason: str


@router.put("/signal-rules")
async def update_signal_rule(
    body: UpdateSignalRuleRequest,
    current_user: User = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SignalRule).where(SignalRule.rule_name == body.rule_name)
    )
    rule = result.scalar_one_or_none()

    if rule:
        rule.previous_value = rule.rule_value
        rule.rule_value = {"value": body.value}
        rule.changed_by = "ADMIN"
        rule.change_reason = body.reason
        rule.updated_at = datetime.now(timezone.utc)
    else:
        rule = SignalRule(
            rule_name=body.rule_name,
            rule_value={"value": body.value},
            changed_by="ADMIN",
            change_reason=body.reason,
        )
        db.add(rule)

    await db.commit()
    return {"rule": rule, "message": f"Rule '{body.rule_name}' updated"}
