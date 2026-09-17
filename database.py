"""
База данных через Postgres.
"""
import os
import asyncpg
from datetime import datetime, timedelta
from typing import Optional, Dict, List

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: Optional[asyncpg.Pool] = None


async def init_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL не задан в переменных окружения!")
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _pool_or_raise() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Пул БД не инициализирован.")
    return _pool


class Database:
    def __init__(self):
        self.pool = _pool_or_raise()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1", telegram_id
            )
            return dict(row) if row else None

    async def create_user(self, telegram_id: int, username, full_name,
                          referrer_id=None) -> Optional[Dict]:
        trial_until = datetime.now() + timedelta(days=7)
        async with self.pool.acquire() as conn:
            if referrer_id:
                ref_exists = await conn.fetchval(
                    "SELECT 1 FROM users WHERE telegram_id = $1", referrer_id
                )
                if not ref_exists:
                    referrer_id = None
            await conn.execute("""
                INSERT INTO users (telegram_id, username, full_name, trial_until, referrer_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (telegram_id) DO NOTHING
            """, telegram_id, username, full_name, trial_until, referrer_id)
            if referrer_id and referrer_id != telegram_id:
                try:
                    await conn.execute("""
                        INSERT INTO referrals (referrer_id, referred_id)
                        VALUES ($1, $2)
                    """, referrer_id, telegram_id)
                    await conn.execute("""
                        UPDATE users SET balance = balance + 100
                        WHERE telegram_id = $1
                    """, referrer_id)
                except asyncpg.UniqueViolationError:
                    pass
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1", telegram_id
            )
            return dict(row) if row else None

async def update_user_status(self, telegram_id: int, status: str, months: int = None):
    async with self.pool.acquire() as conn:
        if status == "premium_forever":
            await conn.execute("""
                UPDATE users
                SET status='premium_forever', trial_until=NULL, premium_until=NULL
                WHERE telegram_id=$1
            """, telegram_id)
        elif status == "premium" and months:
            existing = await conn.fetchval(
                "SELECT premium_until FROM users WHERE telegram_id=$1", telegram_id
            )
            base = datetime.now()
            if existing and existing > base:
                base = existing
            premium_until = base + timedelta(days=30 * months)
            await conn.execute("""
                UPDATE users
                SET status='premium', premium_until=$1, trial_until=NULL
                WHERE telegram_id=$2
            """, premium_until, telegram_id)
        else:
            await conn.execute("""
                UPDATE users
                SET status=$1, trial_until=NULL, premium_until=NULL
                WHERE telegram_id=$2
            """, status, telegram_id)

async def get_all_users(self) -> List[Dict]:
    async with self.pool.acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id, status FROM users")
        return [dict(r) for r in rows]

async def count_users(self) -> int:
    async with self.pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")

async def count_premium(self) -> int:
    async with self.pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE status IN ('premium','premium_forever')"
        )

async def add_balance(self, telegram_id: int, amount: int):
    async with self.pool.acquire() as conn:
        await conn.execute("""
            UPDATE users SET balance = balance + $1 WHERE telegram_id = $2
        """, amount, telegram_id)

async def get_today_orders_count(self, telegram_id: int) -> int:
    async with self.pool.acquire() as conn:
        return await conn.fetchval("""
            SELECT COUNT(*) FROM orders
            WHERE user_id=$1 AND DATE(created_at)=CURRENT_DATE
        """, telegram_id)

async def create_order(self, telegram_id: int, category: str,
                       description: str, contacts: str):
    async with self.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO orders (user_id, category, description, budget, contacts)
            VALUES ($1, $2, $3, 0, $4)
        """, telegram_id, category, description, contacts)

async def get_referrals_count(self, telegram_id: int) -> int:
    async with self.pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=$1", telegram_id
        )

async def get_user_categories(self, telegram_id: int) -> List[str]:
    async with self.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT category FROM user_categories WHERE user_id=$1", telegram_id
        )
        return [r['category'] for r in rows]

async def toggle_user_category(self, telegram_id: int, category: str):
    async with self.pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM user_categories WHERE user_id=$1 AND category=$2",
            telegram_id, category
        )
        if exists:
            await conn.execute(
                "DELETE FROM user_categories WHERE user_id=$1 AND category=$2",
                telegram_id, category
            )
        else:
            await conn.execute(
                "INSERT INTO user_categories (user_id, category) VALUES ($1, $2)",
                telegram_id, category
            )

async def create_promocode(self, code: str, action: str, value: int):
    async with self.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO promocodes (code, action, value)
            VALUES ($1, $2, $3)
        """, code, action, value)

async def use_promocode(self, code: str, user_id: int) -> Optional[Dict]:
    async with self.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM promocodes
            WHERE code=$1 AND used_by IS NULL
        """, code)
        if not row:
            return None
        await conn.execute(
            "UPDATE promocodes SET used_by=$1 WHERE code=$2",
            user_id, code
        )
        return dict(row)

async def create_ad(self, user_id: int, ad_text: str, media_type: str,
                    media_id: str, button_text: str, button_url: str):
    async with self.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO ads (user_id, ad_text, media_type, media_id,
                             button_text, button_url)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, user_id, ad_text, media_type, media_id, button_text, button_url)

async def mark_last_ad_paid(self, user_id: int):
    async with self.pool.acquire() as conn:
        await conn.execute("""
            UPDATE ads SET status='paid', payment_tx='manual'
            WHERE id = (
                SELECT id FROM ads
                WHERE user_id=$1 AND status='pending'
                ORDER BY id DESC LIMIT 1
            )
        """, user_id)

async def create_parsed_order(self, source_chat, source_chat_title,
                               author_id, author_username, author_name,
                               message_id, message_text, message_link, category):
    async with self.pool.acquire() as conn:
        return await conn.fetchval("""
            INSERT INTO parsed_orders
            (source_chat, source_chat_title, author_id, author_username,
             author_name, message_id, message_text, message_link, category)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """, source_chat, source_chat_title, author_id, author_username,
            author_name, message_id, message_text, message_link, category)

async def is_message_already_parsed(self, source_chat: str, message_id: int) -> bool:
    async with self.pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT 1 FROM parsed_orders WHERE source_chat=$1 AND message_id=$2",
            source_chat, message_id
        )
        return row is not None
