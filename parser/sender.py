"""
Рассылка найденных заявок юзерам бота.
Учитывает их выбор категорий.
"""
import asyncio
import logging

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import Database


logger = logging.getLogger(__name__)


async def broadcast_parsed_order(bot, parsed_order_id: int):
    """
    Отправляет найденную заявку всем юзерам бота.
    Юзерам с фильтром категорий — только релевантные.
    """
    with Database() as db:
        cur = db.conn.cursor()
        cur.execute("SELECT * FROM parsed_orders WHERE id=?", (parsed_order_id,))
        row = cur.fetchone()
        if not row:
            logger.warning(f"parsed_order {parsed_order_id} не найден")
            return
        order = dict(row)
        users = db.get_all_users()

    category = order['category']
    text = order['message_text'] or ''

    # Обрезаем длинный текст
    if len(text) > 700:
        text = text[:700] + "..."

    # Кнопки
    buttons = []
    if order['author_username']:
        buttons.append([InlineKeyboardButton(
            text="💬 Написать автору",
            url=f"https://t.me/{order['author_username']}"
        )])
    if order['message_link']:
        buttons.append([InlineKeyboardButton(
            text="👁 Открыть в Telegram",
            url=order['message_link']
        )])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    # Текст сообщения
    author = order['author_username'] and f"@{order['author_username']}"
    if not author:
        author = order['author_name'] or f"ID: {order['author_id']}"

    source = order['source_chat_title'] or order['source_chat']
    if order['source_chat_title'] and order['source_chat']:
        source = f"{order['source_chat_title']} ({order['source_chat']})"

    msg = (
        f"🔎 НОВАЯ ЗАЯВКА ИЗ ЧАТА\n\n"
        f"📂 Категория: {category}\n\n"
        f"📝 Текст:\n{text}\n\n"
        f"📢 Источник: {source}\n"
        f"👤 От: {author}"
    )

    sent_count = 0
    for u in users:
        try:
            # Фильтр по категориям для премиум-юзеров
            if u['status'] == 'premium':
                with Database() as db2:
                    user_cats = db2.get_user_categories(u['telegram_id'])
                if user_cats and category not in user_cats:
                    continue

            await bot.send_message(u['telegram_id'], msg,
                                   reply_markup=keyboard,
                                   disable_web_page_preview=True)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.debug(f"Не отправлено {u['telegram_id']}: {e}")
            continue

    logger.info(f"Заявка {parsed_order_id} разослана {sent_count} юзерам")