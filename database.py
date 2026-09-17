import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List

DB_NAME = "bot.db"


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'trial',
            trial_until DATETIME,
            premium_until DATETIME,
            balance INTEGER DEFAULT 0,
            referrer_id INTEGER,
            reg_date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            description TEXT,
            budget INTEGER,
            contacts TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            UNIQUE(user_id, category)
        );
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad_text TEXT,
            media_type TEXT,
            media_id TEXT,
            button_text TEXT,
            button_url TEXT,
            status TEXT DEFAULT 'pending',
            payment_tx TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            action TEXT,
            value INTEGER,
            used_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS parser_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            session_string TEXT,
            phone TEXT,
            is_active INTEGER DEFAULT 0,
            chats_count INTEGER DEFAULT 0,
            last_error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS parsed_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_chat TEXT,
            source_chat_title TEXT,
            author_id INTEGER,
            author_username TEXT,
            author_name TEXT,
            message_id INTEGER,
            message_text TEXT,
            message_link TEXT,
            category TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.conn.close()

    # ---------- USERS ----------
    def get_user(self, telegram_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def create_user(self, telegram_id, username, full_name, referrer_id=None):
        trial_until = datetime.now() + timedelta(days=7)
        cur = self.conn.cursor()
        if referrer_id:
            cur.execute("SELECT 1 FROM users WHERE telegram_id = ?", (referrer_id,))
            if not cur.fetchone():
                referrer_id = None
        cur.execute("""
            INSERT OR IGNORE INTO users (telegram_id, username, full_name, trial_until, referrer_id)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, username, full_name, trial_until, referrer_id))
        self.conn.commit()
        if referrer_id and referrer_id != telegram_id:
            try:
                cur.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                            (referrer_id, telegram_id))
                cur.execute("UPDATE users SET balance = balance + 100 WHERE telegram_id = ?",
                            (referrer_id,))
                self.conn.commit()
            except sqlite3.IntegrityError:
                pass
        return self.get_user(telegram_id)

    def update_user_status(self, telegram_id, status, months=None):
        cur = self.conn.cursor()
        if status == "premium_forever":
            cur.execute(
                "UPDATE users SET status='premium_forever', trial_until=NULL, premium_until=NULL "
                "WHERE telegram_id=?", (telegram_id,))
        elif status == "premium" and months:
            cur.execute("SELECT premium_until FROM users WHERE telegram_id=?", (telegram_id,))
            row = cur.fetchone()
            base = datetime.now()
            if row and row['premium_until']:
                try:
                    existing = datetime.fromisoformat(row['premium_until'])
                    if existing > base:
                        base = existing
                except (ValueError, TypeError):
                    pass
            premium_until = base + timedelta(days=30 * months)
            cur.execute(
                "UPDATE users SET status='premium', premium_until=?, trial_until=NULL "
                "WHERE telegram_id=?", (premium_until, telegram_id))
        else:
            cur.execute(
                "UPDATE users SET status=?, trial_until=NULL, premium_until=NULL "
                "WHERE telegram_id=?", (status, telegram_id))
        self.conn.commit()

    def get_all_users(self) -> List[Dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT telegram_id, status FROM users")
        return [dict(r) for r in cur.fetchall()]

    def count_users(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM users")
        return cur.fetchone()['c']

    def count_premium(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM users WHERE status IN ('premium','premium_forever')")
        return cur.fetchone()['c']

    def add_balance(self, telegram_id, amount):
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
                    (amount, telegram_id))
        self.conn.commit()

    # ---------- ORDERS ----------
    def get_today_orders_count(self, telegram_id):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) AS c FROM orders
            WHERE user_id=? AND DATE(created_at)=DATE('now')
        """, (telegram_id,))
        return cur.fetchone()['c']

    def create_order(self, telegram_id, category, description, contacts):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO orders (user_id, category, description, budget, contacts)
            VALUES (?, ?, ?, 0, ?)
        """, (telegram_id, category, description, contacts))
        self.conn.commit()

    # ---------- REFERRALS ----------
    def get_referrals_count(self, telegram_id):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id=?", (telegram_id,))
        return cur.fetchone()['c']

    # ---------- CATEGORIES ----------
    def get_user_categories(self, telegram_id):
        cur = self.conn.cursor()
        cur.execute("SELECT category FROM user_categories WHERE user_id=?", (telegram_id,))
        return [r['category'] for r in cur.fetchall()]

    def toggle_user_category(self, telegram_id, category):
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM user_categories WHERE user_id=? AND category=?",
                    (telegram_id, category))
        if cur.fetchone():
            cur.execute("DELETE FROM user_categories WHERE user_id=? AND category=?",
                        (telegram_id, category))
        else:
            cur.execute("INSERT INTO user_categories (user_id, category) VALUES (?, ?)",
                        (telegram_id, category))
        self.conn.commit()

    # ---------- PROMOCODES ----------
    def create_promocode(self, code, action, value):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO promocodes (code, action, value) VALUES (?, ?, ?)",
                    (code, action, value))
        self.conn.commit()

    def use_promocode(self, code, user_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM promocodes WHERE code=? AND used_by IS NULL", (code,))
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("UPDATE promocodes SET used_by=? WHERE code=?", (user_id, code))
        self.conn.commit()
        return dict(row)

    # ---------- ADS ----------
    def create_ad(self, user_id, ad_text, media_type, media_id, button_text, button_url):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO ads (user_id, ad_text, media_type, media_id, button_text, button_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, ad_text, media_type, media_id, button_text, button_url))
        self.conn.commit()

    def mark_last_ad_paid(self, user_id):
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE ads SET status='paid', payment_tx='manual'
            WHERE id = (SELECT id FROM ads WHERE user_id=? AND status='pending'
                        ORDER BY id DESC LIMIT 1)
        """, (user_id,))
        self.conn.commit()

    # ---------- PARSER SESSIONS ----------
    def get_parser_session(self, telegram_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM parser_sessions WHERE telegram_id=?", (telegram_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def save_parser_session(self, telegram_id, session_string, phone):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO parser_sessions (telegram_id, session_string, phone, is_active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(telegram_id) DO UPDATE SET
                session_string=excluded.session_string,
                phone=excluded.phone,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (telegram_id, session_string, phone))
        self.conn.commit()

    def deactivate_parser_session(self, telegram_id):
        cur = self.conn.cursor()
        cur.execute("UPDATE parser_sessions SET is_active=0, updated_at=CURRENT_TIMESTAMP "
                    "WHERE telegram_id=?", (telegram_id,))
        self.conn.commit()

    def update_parser_stats(self, telegram_id, chats_count=None, last_error=None):
        cur = self.conn.cursor()
        if chats_count is not None:
            cur.execute("UPDATE parser_sessions SET chats_count=?, updated_at=CURRENT_TIMESTAMP "
                        "WHERE telegram_id=?", (chats_count, telegram_id))
        if last_error is not None:
            cur.execute("UPDATE parser_sessions SET last_error=?, updated_at=CURRENT_TIMESTAMP "
                        "WHERE telegram_id=?", (last_error, telegram_id))
        self.conn.commit()

    def get_all_active_sessions(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM parser_sessions WHERE is_active=1")
        return [dict(r) for r in cur.fetchall()]

    # ---------- PARSED ORDERS ----------
    def create_parsed_order(self, source_chat, source_chat_title, author_id,
                            author_username, author_name, message_id,
                            message_text, message_link, category):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO parsed_orders
            (source_chat, source_chat_title, author_id, author_username,
             author_name, message_id, message_text, message_link, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (source_chat, source_chat_title, author_id, author_username,
              author_name, message_id, message_text, message_link, category))
        self.conn.commit()
        return cur.lastrowid

    def is_message_already_parsed(self, source_chat, message_id):
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM parsed_orders WHERE source_chat=? AND message_id=?",
                    (source_chat, message_id))
        return cur.fetchone() is not None


init_db()