"""Dedicated market worker runtime."""

import asyncio
import logging
import signal

from bot.scheduler import start_scheduler, stop_scheduler
from config import settings
from core.log_buffer import setup_ws_log_handler

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)
setup_ws_log_handler()


async def main():
    logger.info(
        "Starting market worker execution_mode=%s instance=%s",
        settings.execution_mode,
        settings.service_instance_id,
    )
    await start_scheduler()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        await stop_scheduler()
        logger.info("Market worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
