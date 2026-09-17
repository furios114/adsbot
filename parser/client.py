"""
Telethon-клиент для парсинга Telegram-чатов.
Слушает все диалоги аккаунта (до PARSER_MAX_CHATS), находит заявки.
"""
import asyncio
import logging
import os

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from config import API_ID, API_HASH, PARSER_MAX_CHATS
from database import Database
from parser.matcher import classify, is_relevant, make_message_link
from parser.sender import broadcast_parsed_order


logger = logging.getLogger(__name__)

SESSION_FILE = "parser_session.txt"


def _load_session() -> str:
    """Загружает сессию из файла или переменной окружения."""
    env_session = os.getenv("TG_SESSION_STRING")
    if env_session:
        return env_session
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _save_session(session_string: str):
    """Сохраняет сессию в файл."""
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(session_string)
    logger.info("Сессия парсера сохранена")


class ParserClient:
    """Обёртка над Telethon-клиентом."""
    def __init__(self, bot):
        self.bot = bot
        self.client = None
        self.ready = False
        self.chats_count = 0

    async def start(self):
        """Запускает парсер. Требует, чтобы session_string уже была в файле."""
        if API_ID == 0 or not API_HASH or API_HASH.startswith("PASTE"):
            logger.warning("Парсер не запущен: не заданы API_ID / API_HASH в config.py")
            return

        session_string = _load_session()
        if not session_string:
            logger.warning("Парсер не запущен: нет сохранённой сессии. "
                           "Запусти `python login.py` один раз.")
            return

        try:
            self.client = TelegramClient(
                StringSession(session_string),
                API_ID, API_HASH
            )
            await self.client.connect()
            if not await self.client.is_user_authorized():
                logger.error("Сессия парсера не авторизована. Запусти `python login.py`")
                return

            me = await self.client.get_me()
            logger.info(f"Парсер подключён как @{me.username or me.id}")

            # Собираем список чатов
            await self._collect_chats()

            # Подписываемся на новые сообщения
            self.client.add_event_handler(
                self._on_new_message,
                events.NewMessage(incoming=True)
            )

            self.ready = True
            logger.info(f"Парсер запущен, слушает {self.chats_count} чатов")

        except Exception as e:
            logger.exception(f"Ошибка запуска парсера: {e}")

    async def _collect_chats(self):
        """Собирает список групп и каналов (без личных чатов), до лимита."""
        chats = []
        async for dialog in self.client.iter_dialogs(limit=None):
            entity = dialog.entity
            # Только группы и каналы
            if dialog.is_group or dialog.is_channel:
                # Пропускаем каналы с односторонним вещанием? 
                # Нет, оставляем — там тоже бывают заявки.
                chats.append(dialog)
                if len(chats) >= PARSER_MAX_CHATS:
                    break
        self._chats = chats
        self.chats_count = len(chats)
        logger.info(f"Собрано {self.chats_count} чатов/каналов")

    async def _on_new_message(self, event):
        """Обработчик нового сообщения."""
        try:
            text = event.message.message or ""
            if not is_relevant(text):
                return

            category = classify(text)
            if not category:
                return

            # Проверка дубликата
            chat_id = event.chat_id
            msg_id = event.message.id
            chat_key = str(chat_id)
            with Database() as db:
                if db.is_message_already_parsed(chat_key, msg_id):
                    return

            # Метаданные
            sender = await event.get_sender()
            author_id = sender.id if sender else 0
            author_username = getattr(sender, 'username', None)
            author_name = ""
            if sender:
                author_name = f"{getattr(sender, 'first_name', '') or ''} " \
                              f"{getattr(sender, 'last_name', '') or ''}".strip()

            chat = await event.get_chat()
            chat_username = getattr(chat, 'username', None)
            chat_title = getattr(chat, 'title', None) or ""

            message_link = ""
            if chat_username:
                message_link = make_message_link(chat_username, msg_id)

            # Сохранение в БД
            with Database() as db:
                parsed_id = db.create_parsed_order(
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

            logger.info(f"Найдена заявка [{category}] в {chat_title or chat_username}")

            # Рассылка юзерам
            await broadcast_parsed_order(self.bot, parsed_id)

        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds}с, сплю...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.exception(f"Ошибка обработки сообщения: {e}")

    async def stop(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass