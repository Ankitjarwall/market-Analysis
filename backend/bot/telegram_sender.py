"""
Telegram message formatting and sending.
"""

import logging
from datetime import date, datetime

from config import settings

logger = logging.getLogger(__name__)

_bot = None


def _get_bot():
    global _bot
    if _bot is None and settings.telegram_bot_token:
        try:
            from telegram import Bot
            _bot = Bot(token=settings.telegram_bot_token)
        except Exception as exc:
            logger.warning(f"Telegram bot init failed: {exc}")
    return _bot


async def send_message(text: str, chat_ids: list[int] | None = None):
    """Send a text message to all configured chat IDs."""
    bot = _get_bot()
    if not bot:
        logger.debug("Telegram not configured, skipping message")
        return

    targets = chat_ids or settings.telegram_chat_id_list
    for chat_id in targets:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.error(f"Telegram send failed to {chat_id}: {exc}")


async def send_signal_message(signal: dict, position: dict):
    """Format and send the options signal message."""
    ltp = signal.get("ltp_at_signal", 0)
    t1 = signal.get("target1", 0)
    t2 = signal.get("target2", 0)
    sl = signal.get("stop_loss", 0)
    t1_pct = ((t1 - ltp) / ltp * 100) if ltp else 0
    t2_pct = ((t2 - ltp) / ltp * 100) if ltp else 0
    sl_pct = ((ltp - sl) / ltp * 100) if ltp else 0

    rec = position.get("recommended", {})
    partial = position.get("partial_exit_plan", {})
    basis = signal.get("signal_basis", [])

    text = (
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ OPTIONS SIGNAL | {datetime.now().strftime('%H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"TYPE   : {signal.get('signal_type', '').replace('BUY_', 'BUY ')}\n"
        f"STRIKE : {signal.get('strike')} {signal.get('option_type')}\n"
        f"EXPIRY : {signal.get('expiry')}\n"
        f"LTP    : ₹{ltp}\n\n"
        f"🎯 T1  : ₹{t1} (+{t1_pct:.1f}%)\n"
        f"🎯 T2  : ₹{t2} (+{t2_pct:.1f}%)\n"
        f"🛑 SL  : ₹{sl} (-{sl_pct:.1f}%)\n"
        f"📊 R:R : 1:{position.get('rr_ratio', 0):.1f} ✓\n\n"
        f"💰 FOR ₹{rec.get('premium', 0):,.0f}:\n"
        f"  Rec: {rec.get('lots', 1)} lots | Premium ₹{rec.get('premium', 0):,.0f}\n"
        f"  Max loss: ₹{rec.get('max_loss', 0):,.0f} ({rec.get('max_loss_pct', 0):.1f}%)\n"
        f"  T1 profit: +₹{rec.get('profit_t1', 0):,.0f}\n"
        f"  Smart: Book {partial.get('exit_at_t1_lots', 1)} at T1, "
        f"hold {partial.get('hold_to_t2_lots', 0)} to T2\n\n"
    )
    for i, b in enumerate(basis[:3]):
        prefix = "📌" if i == 0 else "  "
        text += f"{prefix} {b}\n"

    text += (
        f"\n🔢 Confidence: {signal.get('confidence', 0)}%\n"
        f"⏱ Valid: 90 min\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"[AUTO MODE: Trade logged]"
    )
    await send_message(text)


async def send_auto_trade_opened(user_chat_id: str, trade: dict, signal: dict):
    msg = (
        f"⚡ AUTO TRADE OPENED\n"
        f"{signal.get('strike')} {signal.get('option_type')} · "
        f"₹{signal.get('ltp_at_signal')} · {trade.get('lots')} lots\n"
        f"T1: ₹{signal.get('target1')} | T2: ₹{signal.get('target2')} | "
        f"SL: ₹{signal.get('stop_loss')}\n"
        f"Max loss: ₹{trade.get('max_loss_calculated', 0):,.0f} "
        f"({trade.get('max_loss_pct', 0):.2f}% of capital)\n"
        f"Bot is monitoring every 30 seconds."
    )
    if user_chat_id:
        try:
            await send_message(msg, chat_ids=[int(user_chat_id)])
        except (ValueError, TypeError):
            pass
