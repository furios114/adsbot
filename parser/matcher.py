"""
Классификатор сообщений из чатов.
Определяет, является ли сообщение заявкой, и к какой категории относится.
"""
import re

from config import PARSER_KEYWORDS, PARSER_STOP_WORDS


# Компилируем регулярки один раз при старте
_KEYWORD_PATTERNS = {}
for category, words in PARSER_KEYWORDS.items():
    # Ищем любое из слов как отдельную фразу (без учёта регистра)
    pattern = "|".join(re.escape(w.lower()) for w in words)
    _KEYWORD_PATTERNS[category] = re.compile(pattern, re.IGNORECASE)


_STOP_PATTERN = re.compile(
    "|".join(re.escape(w.lower()) for w in PARSER_STOP_WORDS),
    re.IGNORECASE
) if PARSER_STOP_WORDS else None


def classify(text: str):
    """
    Возвращает категорию или None.
    Если сообщение содержит стоп-слово — None.
    Если ни одна категория не подходит — None.
    Если подходит несколько категорий — возвращает первую по порядку из config.
    """
    if not text:
        return None

    # Проверка стоп-слов
    if _STOP_PATTERN and _STOP_PATTERN.search(text):
        return None

    text_lower = text.lower()

    for category in PARSER_KEYWORDS.keys():
        pattern = _KEYWORD_PATTERNS[category]
        if pattern.search(text_lower):
            return category

    return None


def is_relevant(text: str) -> bool:
    """Проверка, стоит ли вообще обрабатывать сообщение."""
    if not text:
        return False
    if len(text.strip()) < 15:
        return False
    if len(text) > 3000:
        return False
    return True


def make_message_link(chat_username: str, message_id: int) -> str:
    """Строит ссылку на сообщение в публичном чате."""
    if chat_username:
        return f"https://t.me/{chat_username}/{message_id}"
    return ""