"""
Watchdog — logs service status only. No auto-fix. No auto-deploy.
Self-healing has been removed. Only logging remains.
"""
import logging

logger = logging.getLogger(__name__)


async def start_watchdog():
    """No-op — self-healing removed. Logging is handled by application logger."""
    logger.info("Watchdog disabled — self-healing removed. Use structured logs for monitoring.")


async def run_watchdog_check():
    """No-op — retained for import compatibility only."""
    pass
