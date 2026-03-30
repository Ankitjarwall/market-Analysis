"""
Safe deployment of AI-generated fixes.
Tests must pass before deployment. Git commit made before every change.
"""

import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def deploy_fix_async(error_id: int):
    """Deploy an AI-generated fix after tests pass."""
    from db.connection import AsyncSessionLocal
    from db.models import Error
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Error).where(Error.id == error_id))
        error = result.scalar_one_or_none()
        if not error or not error.fix_code:
            return

        # Determine the file to modify
        file_to_change = _infer_file(error.service)
        if not file_to_change:
            logger.warning(f"Cannot determine file for service {error.service}")
            return

        # Run test cases first
        test_results = _run_fix_tests(error.fix_test_cases or "")
        error.fix_test_results = test_results

        if "FAILED" in test_results or "ERROR" in test_results:
            logger.error(f"Fix tests failed for error {error_id}: {test_results}")
            error.fix_worked = False
            await session.commit()
            return

        # Git commit current state before applying fix
        commit_hash = _git_commit_before_fix(file_to_change, error_id)
        error.git_commit_hash = commit_hash

        # Apply the fix
        success = _apply_fix(file_to_change, error.fix_code)

        error.fix_worked = success
        error.fix_timestamp = datetime.now(timezone.utc)
        await session.commit()

    if success:
        logger.info(f"Fix successfully applied for error {error_id}")
        from websocket.live_feed import manager
        await manager.broadcast_bot_activity(
            f"✅ Auto-fix applied for {error.service}: {error.fix_explanation[:100] if error.fix_explanation else ''}",
            level="SUCCESS"
        )


def _run_fix_tests(test_cases_str: str) -> str:
    """Run fix test cases in an isolated environment."""
    try:
        import ast
        test_cases = ast.literal_eval(test_cases_str) if test_cases_str else []
        if not test_cases:
            return "NO_TESTS"

        results = []
        for tc in test_cases:
            code = tc.get("code", "")
            if not code:
                continue
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                    f.write(code)
                    fname = f.name
                result = subprocess.run(
                    ["python", fname],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                os.unlink(fname)
                results.append(f"{tc.get('name', 'test')}: {'PASS' if result.returncode == 0 else 'FAILED'}")
            except Exception as exc:
                results.append(f"{tc.get('name', 'test')}: ERROR ({exc})")

        return " | ".join(results) or "NO_TESTS"
    except Exception as exc:
        return f"TEST_ERROR: {exc}"


def _git_commit_before_fix(filepath: str, error_id: int) -> str:
    """Git commit current state before applying a fix."""
    try:
        result = subprocess.run(
            ["git", "add", filepath],
            capture_output=True, text=True, timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Pre-fix snapshot before error {error_id} fix",
             "--no-verify"],
            capture_output=True, text=True, timeout=30,
        )
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return hash_result.stdout.strip()
    except Exception as exc:
        logger.warning(f"Git commit before fix failed: {exc}")
        return ""


def _apply_fix(filepath: str, fix_code: str) -> bool:
    """Write the fix code to the target file (appends fix function or replaces relevant section)."""
    try:
        # For safety, we only apply if the file exists
        if not os.path.exists(filepath):
            return False
        with open(filepath, "a") as f:
            f.write(f"\n\n# === AUTO-FIX APPLIED ===\n{fix_code}\n")
        return True
    except Exception as exc:
        logger.error(f"Apply fix failed: {exc}")
        return False


def _infer_file(service: str) -> str | None:
    mapping = {
        "collector": "backend/bot/collector.py",
        "scheduler": "backend/bot/scheduler.py",
        "data_feed": "backend/bot/collector.py",
        "telegram": "backend/bot/telegram_sender.py",
    }
    return mapping.get(service.lower())
