"""Dedicated execution worker runtime."""

import asyncio
import logging
import signal

from bot.angel_feed import start_feed, stop_feed
from bot.trade_handler import reconcile_open_trade_monitors
from config import settings
from core.log_buffer import setup_ws_log_handler

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)
setup_ws_log_handler()


async def main():
    logger.info(
        "Starting execution worker execution_mode=%s instance=%s",
        settings.execution_mode,
        settings.service_instance_id,
    )
    await start_feed()

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
        while not stop_event.is_set():
            open_trade_count = await reconcile_open_trade_monitors()
            logger.debug("Execution worker monitor sweep open_trades=%s", open_trade_count)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                continue
    finally:
        stop_feed()
        logger.info("Execution worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
