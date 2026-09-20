"""
Воркер рассылки: раз в N секунд берёт 1 неотправленную заявку
и шлёт всем админам в ЛС.
"""
import asyncio
import logging

from database import Database

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 600  # 10 минут


def _format_message(order: dict) -> str:
    text = order.get("message_text", "")
    chat = order.get("source_chat_title") or order.get("source_chat") or "?"
    author = order.get("author_username")
    author_str = f"@{author}" if author else (order.get("author_name") or "—")
    link = order.get("message_link") or ""

    msg = (
        f"💬 <b>{chat}</b>\n"
        f"👤 {author_str}\n\n"
        f"{text}"
    )
    if link:
        msg += f"\n\n🔗 <a href='{link}'>Открыть в Telegram</a>"
    return msg


async def broadcast_worker(bot, admin_ids, interval: int = INTERVAL_SECONDS):
    logger.info(f"Воркер рассылки запущен, интервал {interval}с")
    while True:
        try:
            async with Database() as db:
                orders = await db.get_unsent_parsed_orders(limit=1)

            if orders:
                order = orders[0]
                text = _format_message(order)
                for admin_id in admin_ids:
                    try:
                        await bot.send_message(
                            admin_id, text,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                    except Exception as e:
                        logger.warning(f"Не доставлено {admin_id}: {e}")

                async with Database() as db:
                    await db.mark_parsed_order_sent(order["id"])
                logger.info(f"[SENT] #{order['id']} → админам")
            else:
                logger.debug("Очередь пуста")

        except Exception as e:
            logger.error(f"Ошибка воркера: {e}")

        await asyncio.sleep(interval)