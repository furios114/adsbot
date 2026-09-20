"""
Telethon-клиент: читает сообщения из чатов, фильтрует,
классифицирует по категориям и пишет в БД.
Рассылка — отдельным воркером (parser/dispatcher.py).
"""
import asyncio
import logging
import os
import random
import re
import traceback

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from config import (API_ID, API_HASH, PARSER_MAX_CHATS,
                    PARSER_KEYWORDS, PARSER_STOP_WORDS)
from database import Database

logger = logging.getLogger(__name__)

SESSION_FILE = "parser_session.txt"

BACKFILL_ENABLED = True
BACKFILL_MESSAGES_PER_CHAT = 50
BACKFILL_DELAY_BETWEEN_CHATS = (2, 5)
BACKFILL_DELAY_BETWEEN_MSGS = (0.5, 1.5)

MIN_TEXT_LENGTH = 20

# ==================== ЦЕНЗУРА ====================
# Мат и чернуха — если найдено, сообщение отбрасывается
BAD_WORDS = [
    # мат (корни)
    "хуй", "хуе", "хуё", "пизд", "бляд", "блят", "ебал", "ебан", "ебат",
    "ебуч", "ёб", "залуп", "муд", "манда", "пидор", "пидар", "пидр",
    "шлюх", "сука", "сучк", "мраз", "гнид", "долбоёб", "долбоеб",
    "уеб", "уёб", "выеб", "наеб", "отъеб", "подъеб", "разъеб",
    # чернуха / криминал
    "нарко", "мефедрон", "меф", "героин", "кокаин", "спайс", "соль",
    "закладк", "клад", "заклад", "трамал", "амфетамин",
    "убийств", "расстрел", "теракт", "взрыв", "суицид",
    "детск порн", "цп", "cp", "инцест", "педофил",
    "скам", "мошенничеств", "обнал", "отмыв", "фейк паспорт",
    "продам оружие", "куплю оружие", "автомат", "пистолет",
    # реклама / спам-маркеры
    "подписывайтесь", "подпишись", "подписка на канал",
    "продам канал", "продаю канал", "продам группу",
    "казино", "букмекер", "ставки на спорт", "1xbet", "1win",
    "букмекерск", "беттинг",
]


def is_clean(text: str) -> bool:
    """False, если в тексте есть мат/чернуха/явный спам."""
    low = text.lower()
    return not any(w in low for w in BAD_WORDS)


# ==================== ФИЛЬТР РЕЛЕВАНТНОСТИ ====================
def _all_keywords():
    for cat, words in PARSER_KEYWORDS.items():
        for w in words:
            yield cat, w


def is_relevant(text: str) -> bool:
    """True, если текст содержит хотя бы одну ключевую фразу."""
    low = text.lower()
    # стоп-слова — если есть, сразу мимо
    for stop in PARSER_STOP_WORDS:
        if stop in low:
            return False
    return any(kw in low for _, kw in _all_keywords())


def classify(text: str) -> str | None:
    """Возвращает категорию заявки или None."""
    low = text.lower()
    # Первое совпадение по категориям
    for cat, words in PARSER_KEYWORDS.items():
        for w in words:
            if w in low:
                return cat
    return None


# ==================== СЕССИЯ ====================
def _load_session() -> str:
    env_session = os.getenv("TG_SESSION_STRING")
    if env_session:
        return env_session
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


class ParserClient:
    def __init__(self, bot):
        self.bot = bot
        self.client = None
        self.ready = False
        self.chats_count = 0
        self._chats = []

    async def start(self):
        if API_ID == 0 or not API_HASH or API_HASH.startswith("PASTE"):
            logger.error("Парсер не запущен: не заданы API_ID / API_HASH")
            return

        session_string = _load_session()
        if not session_string:
            logger.error("Парсер не запущен: нет сессии. Запусти login.py")
            return

        try:
            self.client = TelegramClient(
                StringSession(session_string),
                API_ID, API_HASH,
            )
            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.error("Сессия не авторизована. Запусти login.py")
                return

            me = await self.client.get_me()
            logger.info(f"Парсер подключён как @{me.username or me.id}")

            await self._collect_chats()

            if BACKFILL_ENABLED:
                logger.info("Запуск бэкфилла истории...")
                await self._backfill_history()
                logger.info("Бэкфилл завершён")

            self.client.add_event_handler(
                self._on_new_message,
                events.NewMessage(incoming=True),
            )

            self.ready = True
            logger.info(f"Парсер запущен, слушает {self.chats_count} чатов")

        except Exception as e:
            logger.error(f"Ошибка запуска: {e}\n{traceback.format_exc()}")

    async def _collect_chats(self):
        chats = []
        async for dialog in self.client.iter_dialogs(limit=None):
            if dialog.is_group or dialog.is_channel:
                chats.append(dialog)
                if len(chats) >= PARSER_MAX_CHATS:
                    break
        self._chats = chats
        self.chats_count = len(chats)
        logger.info(f"Собрано {self.chats_count} чатов/каналов")

    async def _backfill_history(self):
        total = len(self._chats)
        for idx, dialog in enumerate(self._chats, 1):
            chat_title = getattr(dialog, "name", None) or str(dialog.id)
            logger.info(f"[BACKFILL {idx}/{total}] {chat_title}")
            try:
                async for msg in self.client.iter_messages(
                    dialog, limit=BACKFILL_MESSAGES_PER_CHAT
                ):
                    try:
                        await self._process_message(msg, dialog.entity)
                    except Exception as e:
                        logger.debug(f"[BACKFILL] ошибка: {e}")
                    await asyncio.sleep(
                        random.uniform(*BACKFILL_DELAY_BETWEEN_MSGS)
                    )
                await asyncio.sleep(
                    random.uniform(*BACKFILL_DELAY_BETWEEN_CHATS)
                )
            except FloodWaitError as e:
                logger.warning(f"[BACKFILL] FloodWait {e.seconds}с")
                await asyncio.sleep(e.seconds + 5)
            except Exception as e:
                logger.error(f"[BACKFILL] ошибка чата {chat_title}: {e}")

    async def _on_new_message(self, event):
        try:
            await self._process_message(event.message, await event.get_chat())
        except Exception as e:
            logger.error(f"[CRASH] {e}\n{traceback.format_exc()}")

    async def _process_message(self, msg, chat):
        text = msg.message or ""
        if len(text) < MIN_TEXT_LENGTH:
            return

        # 1. Цензура
        if not is_clean(text):
            logger.debug(f"[CENSOR] {text[:60]!r}")
            return

        # 2. Релевантность
        if not is_relevant(text):
            return

        # 3. Классификация
        category = classify(text)
        if not category:
            return

        # 4. Автор
        try:
            sender = await msg.get_sender()
        except Exception:
            sender = None

        if sender and getattr(sender, "bot", False):
            return

        chat_id = msg.chat_id if hasattr(msg, "chat_id") else getattr(chat, "id", 0)
        msg_id = msg.id
        chat_key = str(chat_id)

        # 5. Дедупликация
        async with Database() as db:
            if await db.is_message_already_parsed(chat_key, msg_id):
                return

        author_id = sender.id if sender else 0
        author_username = getattr(sender, "username", None)
        author_name = ""
        if sender:
            first = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            author_name = f"{first} {last}".strip()

        chat_username = getattr(chat, "username", None)
        chat_title = getattr(chat, "title", None) or getattr(chat, "name", "") or ""

        message_link = ""
        if chat_username:
            message_link = f"https://t.me/{chat_username}/{msg_id}"

        # 6. Сохранение
        try:
            async with Database() as db:
                await db.create_parsed_order(
                    source_chat=chat_key,
                    source_chat_title=chat_title,
                    author_id=author_id,
                    author_username=author_username,
                    author_name=author_name,
                    message_id=msg_id,
                    message_text=text,
                    message_link=message_link,
                    category=category,
                )
            logger.info(f"[HIT] [{category}] {chat_title} | {text[:60]!r}")
        except Exception as e:
            logger.error(f"[DB] {e}\n{traceback.format_exc()}")

    async def stop(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass