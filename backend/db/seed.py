"""
Seed script — creates the initial super_admin user and default signal rules.
Run via: python -c "from db.seed import seed_admin; import asyncio; asyncio.run(seed_admin())"
"""

import asyncio
import uuid
from datetime import datetime, timezone

from passlib.context import CryptContext

from db.connection import AsyncSessionLocal, engine, Base
from db.models import SignalRule, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_SIGNAL_RULES = [
    {"rule_name": "min_vix_for_put", "rule_value": {"value": 15.0}, "change_reason": "Initial default"},
    {"rule_name": "min_fii_consecutive_days", "rule_value": {"value": 1}, "change_reason": "Relaxed: 1 day FII direction sufficient"},
    {"rule_name": "min_confidence", "rule_value": {"value": 55}, "change_reason": "Initial default"},
    {"rule_name": "min_rr_ratio", "rule_value": {"value": 2.0}, "change_reason": "Initial default"},
    {"rule_name": "max_daily_signals", "rule_value": {"value": 2}, "change_reason": "Initial default"},
    {"rule_name": "signal_cooldown_after_sl_minutes", "rule_value": {"value": 60}, "change_reason": "Initial default"},
    {"rule_name": "max_vix_for_call", "rule_value": {"value": 28.0}, "change_reason": "Initial default"},
    {"rule_name": "pcr_max_for_put", "rule_value": {"value": 0.95}, "change_reason": "Initial default"},
    {"rule_name": "pcr_min_for_call", "rule_value": {"value": 0.70}, "change_reason": "Initial default"},
]


async def seed_admin():
    # Create tables if needed
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        # Check if super_admin exists
        result = await session.execute(
            select(User).where(User.role == "super_admin").limit(1)
        )
        if result.scalar_one_or_none():
            print("Super admin already exists. Skipping.")
            return

        # Create super admin
        admin = User(
            email="admin@marketplatform.io",
            password_hash=pwd_context.hash("Admin@123!"),
            name="Platform Admin",
            role="super_admin",
            capital=200_000,
            trade_mode="manual",
            is_active=True,
        )
        session.add(admin)

        # Create default signal rules
        for rule_data in DEFAULT_SIGNAL_RULES:
            existing = await session.execute(
                select(SignalRule).where(SignalRule.rule_name == rule_data["rule_name"])
            )
            if not existing.scalar_one_or_none():
                rule = SignalRule(
                    rule_name=rule_data["rule_name"],
                    rule_value=rule_data["rule_value"],
                    changed_by="SYSTEM",
                    change_reason=rule_data["change_reason"],
                )
                session.add(rule)

        await session.commit()
        print("✅ Super admin created: admin@marketplatform.io / Admin@123!")
        print("✅ Default signal rules seeded")
        print("")
        print("⚠️ IMPORTANT: Change the admin password immediately after first login!")


if __name__ == "__main__":
    asyncio.run(seed_admin())
