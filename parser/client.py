"""
Telethon-клиент: читает все сообщения из чатов и кладёт в БД.
Рассылка — отдельным воркером (parser/dispatcher.py).
"""
import asyncio
import logging
import os
import random
import traceback

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from config import API_ID, API_HASH, PARSER_MAX_CHATS
from database import Database

logger = logging.getLogger(__name__)

SESSION_FILE = "parser_session.txt"

BACKFILL_ENABLED = True
BACKFILL_MESSAGES_PER_CHAT = 50
BACKFILL_DELAY_BETWEEN_CHATS = (2, 5)
BACKFILL_DELAY_BETWEEN_MSGS = (0.5, 1.5)

MIN_TEXT_LENGTH = 20


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
            logger.error(f"Ошибка запуска парсера: {e}\n{traceback.format_exc()}")

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

        try:
            sender = await msg.get_sender()
        except Exception:
            sender = None

        if sender and getattr(sender, "bot", False):
            return

        chat_id = msg.chat_id if hasattr(msg, "chat_id") else getattr(chat, "id", 0)
        msg_id = msg.id
        chat_key = str(chat_id)

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
                    category="all",
                )
            logger.info(f"[SAVED] {chat_title} | {text[:60]!r}")
        except Exception as e:
            logger.error(f"[DB] {e}\n{traceback.format_exc()}")

    async def stop(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass