"""
Работа с Postgres (asyncpg).
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: Optional[asyncpg.Pool] = None


async def init_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL не задан!")
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _pool_or_raise() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Пул не инициализирован.")
    return _pool


class Database:
    def __init__(self):
        self.pool = _pool_or_raise()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    # ==================== USERS ====================
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1", telegram_id
            )
            return dict(row) if row else None

    async def create_user(self, telegram_id: int, username, full_name,
                          referrer_id=None):
        trial_until = datetime.now() + timedelta(days=7)
        async with self.pool.acquire() as conn:
            if referrer_id:
                ref_exists = await conn.fetchval(
                    "SELECT 1 FROM users WHERE telegram_id = $1", referrer_id
                )
                if not ref_exists:
                    referrer_id = None

            await conn.execute(
                "INSERT INTO users (telegram_id, username, full_name, "
                "trial_until, referrer_id) "
                "VALUES ($1, $2, $3, $4, $5) "
                "ON CONFLICT (telegram_id) DO NOTHING",
                telegram_id, username, full_name, trial_until, referrer_id,
            )

            if referrer_id and referrer_id != telegram_id:
                try:
                    await conn.execute(
                        "INSERT INTO referrals (referrer_id, referred_id) "
                        "VALUES ($1, $2)",
                        referrer_id, telegram_id,
                    )
                    await conn.execute(
                        "UPDATE users SET balance = balance + 100 "
                        "WHERE telegram_id = $1",
                        referrer_id,
                    )
                except asyncpg.UniqueViolationError:
                    pass

            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1", telegram_id
            )
            return dict(row) if row else None

    async def update_user_status(self, telegram_id: int, status: str,
                                 months: int = None):
        async with self.pool.acquire() as conn:
            if status == "premium_forever":
                await conn.execute(
                    "UPDATE users SET status = $1 WHERE telegram_id = $2",
                    status, telegram_id,
                )
                return

            if status == "premium" and months:
                until = datetime.now() + timedelta(days=30 * months)
                await conn.execute(
                    "UPDATE users SET status = $1, premium_until = $2 "
                    "WHERE telegram_id = $3",
                    status, until, telegram_id,
                )
                return

            await conn.execute(
                "UPDATE users SET status = $1 WHERE telegram_id = $2",
                status, telegram_id,
            )

    async def get_all_users(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users")
            return [dict(r) for r in rows]

    async def get_referrals_count(self, telegram_id: int) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1",
                telegram_id,
            )

    # ==================== CATEGORIES ====================
    async def get_user_categories(self, telegram_id: int) -> List[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT category FROM user_categories WHERE telegram_id = $1",
                telegram_id,
            )
            return [r["category"] for r in rows]

    async def toggle_user_category(self, telegram_id: int, category: str):
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM user_categories "
                "WHERE telegram_id = $1 AND category = $2",
                telegram_id, category,
            )
            if exists:
                await conn.execute(
                    "DELETE FROM user_categories "
                    "WHERE telegram_id = $1 AND category = $2",
                    telegram_id, category,
                )
            else:
                await conn.execute(
                    "INSERT INTO user_categories (telegram_id, category) "
                    "VALUES ($1, $2)",
                    telegram_id, category,
                )

    # ==================== ORDERS (пользовательские заявки) ====================
    async def create_order(self, user_id: int, category: str,
                           description: str, contacts: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "INSERT INTO orders (user_id, category, description, contacts) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                user_id, category, description, contacts,
            )

    async def get_today_orders_count(self, user_id: int) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM orders "
                "WHERE user_id = $1 AND created_at::date = CURRENT_DATE",
                user_id,
            )

    # ==================== ADS ====================
    async def create_ad(self, user_id: int, text: str, media_type: str,
                        media_file_id: str, button_text: str, button_url: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "INSERT INTO ads (user_id, text, media_type, media_file_id, "
                "button_text, button_url) "
                "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                user_id, text, media_type, media_file_id,
                button_text, button_url,
            )

    # ==================== PARSED ORDERS ====================
    async def create_parsed_order(self, source_chat, source_chat_title,
                                  author_id, author_username, author_name,
                                  message_id, message_text, message_link,
                                  category):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "INSERT INTO parsed_orders (source_chat, source_chat_title, "
                "author_id, author_username, author_name, message_id, "
                "message_text, message_link, category) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id",
                source_chat, source_chat_title, author_id, author_username,
                author_name, message_id, message_text, message_link, category,
            )

    async def is_message_already_parsed(self, source_chat: str,
                                        message_id: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT 1 FROM parsed_orders "
                "WHERE source_chat = $1 AND message_id = $2",
                source_chat, message_id,
            )
            return row is not None

    async def get_unsent_parsed_orders(self, limit: int = 1) -> List[Dict]:
        """Возвращает неотправленные заявки (старые первыми)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM parsed_orders "
                "WHERE sent = FALSE OR sent IS NULL "
                "ORDER BY id ASC LIMIT $1",
                limit,
            )
            return [dict(r) for r in rows]

    async def mark_parsed_order_sent(self, order_id: int):
        """Помечает заявку как отправленную."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE parsed_orders SET sent = TRUE, sent_at = NOW() "
                "WHERE id = $1",
                order_id,
            )