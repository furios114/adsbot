"""
Воркер рассылки: раз в N секунд берёт 1 неотправленную заявку (атомарно)
и шлёт её ТОЛЬКО тем, кто подписан на категорию + админам.
"""
import asyncio
import logging

from database import Database

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 300  # 5 минут


def _format_message(order: dict) -> str:
    text = order.get("message_text", "")
    chat = order.get("source_chat_title") or order.get("source_chat") or "?"
    author = order.get("author_username")
    author_str = f"@{author}" if author else (order.get("author_name") or "—")
    link = order.get("message_link") or ""
    category = order.get("category") or "—"

    msg = (
        f"📂 <b>{category}</b>\n"
        f"💬 <b>{chat}</b>\n"
        f"👤 {author_str}\n\n"
        f"{text}"
    )
    if link:
        msg += f"\n\n🔗 <a href='{link}'>Открыть в Telegram</a>"
    return msg


async def _get_recipients(category: str) -> list[int]:
    from config import ADMIN_IDS

    async with Database() as db:
        rows = await db.get_users_by_category(category)

    ids = {u["telegram_id"] for u in rows}
    ids.update(ADMIN_IDS)
    return list(ids)


async def broadcast_worker(bot, interval: int = INTERVAL_SECONDS):
    logger.info(f"Воркер рассылки запущен, интервал {interval}с")
    while True:
        try:
            # АТОМАРНО: взять и сразу пометить отправленной
            async with Database() as db:
                order = await db.take_next_unsent_order()

            if not order:
                logger.debug("Очередь пуста")
                await asyncio.sleep(interval)
                continue

            category = order.get("category") or "all"
            text = _format_message(order)
            recipients = await _get_recipients(category)

            logger.info(
                f"[SEND] #{order['id']} [{category}] "
                f"→ {len(recipients)} получателей"
            )

            sent = 0
            for uid in recipients:
                try:
                    await bot.send_message(
                        uid, text,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                    sent += 1
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Не доставлено {uid}: {e}")

            logger.info(f"[SENT] #{order['id']} → {sent}/{len(recipients)}")

        except Exception as e:
            logger.error(f"Ошибка воркера: {e}")

        await asyncio.sleep(interval)