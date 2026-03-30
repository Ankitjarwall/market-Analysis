"""
AI-powered error fixer — asks Claude to analyze and fix production errors.
NEVER touches auth/security code (severity 4 = human only).
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

HEAL_PROMPT = """A production error occurred. Analyze it and provide a fix.

ERROR:
Service:   {service}
Type:      {error_type}
Severity:  {severity}
Traceback:
{traceback}

Last 50 log lines:
{log_context}

Relevant source code:
{source_code}

Similar past errors fixed:
{similar_fixes}

Rules:
- Fix must be minimal — change as little as possible
- Fix must not touch authentication or security code
- Fix must include test cases
- Fix must not change database schema without migration
- If you cannot safely fix this, say so clearly

Output JSON:
{{
  "can_fix": true,
  "reason_if_cannot": "...",
  "file_to_change": "backend/bot/collector.py",
  "original_code": "exact code to replace",
  "fixed_code": "replacement code",
  "explanation": "what was wrong and what the fix does",
  "test_cases": [
    {{"name": "test_name", "code": "def test(): ...", "expected": "passes"}}
  ],
  "risk_level": "LOW|MEDIUM|HIGH",
  "requires_restart": false
}}"""


async def request_ai_fix(error_id: int):
    """Request Claude to fix a severity-3 error."""
    from bot.analyzer import _call_claude_json
    from db.connection import AsyncSessionLocal
    from db.models import Error
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Error).where(Error.id == error_id))
        error = result.scalar_one_or_none()
        if not error:
            return

        if error.severity == 4:
            logger.warning(f"Refusing AI fix for severity 4 error {error_id}")
            return

        # Don't attempt fix on auth/security errors regardless of severity
        if any(kw in error.service.lower() for kw in ("auth", "security", "jwt", "password")):
            logger.warning(f"Refusing AI fix for security-related service: {error.service}")
            return

        # Get source code context
        source_code = _get_source_code(error.service)

        # Get similar past fixes
        similar_result = await session.execute(
            select(Error)
            .where(Error.fix_worked == True)
            .where(Error.error_type == error.error_type)
            .order_by(Error.fix_timestamp.desc())
            .limit(3)
        )
        similar = similar_result.scalars().all()
        similar_text = "\n".join(
            f"- {e.service}: {e.fix_explanation}" for e in similar
        ) or "None"

        prompt = HEAL_PROMPT.format(
            service=error.service,
            error_type=error.error_type,
            severity=error.severity,
            traceback=error.traceback or "N/A",
            log_context=error.log_context or "N/A",
            source_code=source_code,
            similar_fixes=similar_text,
        )

    try:
        analysis = await _call_claude_json(prompt, max_tokens=3000)
    except Exception as exc:
        logger.error(f"Claude fix request failed: {exc}")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Error).where(Error.id == error_id))
        error = result.scalar_one_or_none()
        if not error:
            return

        error.fix_attempted = True
        error.fix_source = "CLAUDE"
        error.fix_code = analysis.get("fixed_code")
        error.fix_explanation = analysis.get("explanation")
        error.fix_test_cases = str(analysis.get("test_cases", []))
        await session.commit()

    if analysis.get("can_fix") and analysis.get("risk_level") == "LOW":
        # Low-risk fixes can be auto-approved
        from healing.deployer import deploy_fix_async
        import asyncio
        asyncio.create_task(deploy_fix_async(error_id))
    else:
        # Broadcast for admin approval
        from websocket.live_feed import manager
        await manager.broadcast_heal_warning({
            "severity": error.severity if error else 3,
            "error_id": error_id,
            "message": f"AI fix ready — requires admin approval",
            "explanation": analysis.get("explanation"),
            "risk_level": analysis.get("risk_level"),
        })

    logger.info(f"AI fix prepared for error {error_id}: {analysis.get('explanation', '')[:100]}")


def _get_source_code(service: str) -> str:
    """Read the source file for a service to provide context to Claude."""
    service_files = {
        "collector": "backend/bot/collector.py",
        "scheduler": "backend/bot/scheduler.py",
        "data_feed": "backend/bot/collector.py",
        "fastapi": "backend/main.py",
        "telegram": "backend/bot/telegram_sender.py",
    }
    filepath = service_files.get(service.lower())
    if not filepath:
        return "Source file not available"
    try:
        with open(filepath, "r") as f:
            content = f.read()
        return content[:3000]  # Limit to 3000 chars
    except Exception:
        return "Source file not available"
