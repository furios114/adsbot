"""
Воркер рассылки: раз в N секунд берёт 1 неотправленную заявку
и шлёт её ТОЛЬКО тем юзерам, у кого выбрана эта категория.
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
    """
    Возвращает список telegram_id юзеров, которые подписаны на категорию.
    Админов добавляем всегда.
    """
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
            async with Database() as db:
                orders = await db.get_unsent_parsed_orders(limit=1)

            if orders:
                order = orders[0]
                category = order.get("category") or "all"
                text = _format_message(order)

                recipients = await _get_recipients(category)
                logger.info(
                    f"[SEND] #{order['id']} [{category}] "
                    f"→ {len(recipients)} получателей"
                )

                for uid in recipients:
                    try:
                        await bot.send_message(
                            uid, text,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                        await asyncio.sleep(0.05)  # антифлуд
                    except Exception as e:
                        logger.warning(f"Не доставлено {uid}: {e}")

                async with Database() as db:
                    await db.mark_parsed_order_sent(order["id"])
            else:
                logger.debug("Очередь пуста")

        except Exception as e:
            logger.error(f"Ошибка воркера: {e}")

        await asyncio.sleep(interval)