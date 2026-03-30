"""
Git-based rollback for when fixes break things.
"""

import logging
import subprocess

logger = logging.getLogger(__name__)


async def perform_rollback() -> dict:
    """Rollback to the last known good git commit."""
    try:
        # Get current commit
        current = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        current_hash = current.stdout.strip()

        # Get parent commit
        parent = subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            capture_output=True, text=True, timeout=10,
        )
        parent_hash = parent.stdout.strip()

        if not parent_hash:
            return {"success": False, "message": "No parent commit to roll back to"}

        # Create a revert commit (safer than reset --hard)
        revert = subprocess.run(
            ["git", "revert", "--no-edit", current_hash],
            capture_output=True, text=True, timeout=60,
        )

        if revert.returncode != 0:
            return {
                "success": False,
                "message": f"Rollback failed: {revert.stderr}",
                "from": current_hash,
            }

        new_hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        new_hash = new_hash_result.stdout.strip()

        logger.info(f"Rollback complete: {current_hash} → {new_hash}")
        return {
            "success": True,
            "message": "Rollback complete",
            "reverted_from": current_hash,
            "new_commit": new_hash,
        }
    except Exception as exc:
        logger.error(f"Rollback error: {exc}", exc_info=True)
        return {"success": False, "message": str(exc)}
