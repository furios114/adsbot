from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, PRICES, CATEGORIES, ORDER_CATEGORIES, SUPPORT_URL
from database import Database


def main_keyboard(user_id: int = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👤 Мой аккаунт", callback_data="menu_account")],
        [InlineKeyboardButton(text="💎 Получить ПРЕМИУМ", callback_data="menu_premium")],
        [InlineKeyboardButton(text="📝 Разместить заявку", callback_data="menu_order")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="menu_referral")],
        [InlineKeyboardButton(text="📢 Разместить рекламу", callback_data="menu_ad")],
        [InlineKeyboardButton(text="📂 Выбор категорий", callback_data="menu_categories")],
        [InlineKeyboardButton(text="🎫 Промокод", callback_data="menu_promo")],
        [InlineKeyboardButton(text="🆘 Техническая поддержка", url=SUPPORT_URL)],
    ]
    if user_id and user_id in ADMIN_IDS:
        rows.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="menu_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👑 Выдать премиум", callback_data="admin_grant")],
        [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton(text="👑 Забрать премиум", callback_data="admin_revoke")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_home")],
    ])


def categories_choice_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=f"ordcat_{label}")]
            for label in ORDER_CATEGORIES]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="menu_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ad_creation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Добавить текст", callback_data="ad_text")],
        [InlineKeyboardButton(text="🖼 Добавить медиа", callback_data="ad_media")],
        [InlineKeyboardButton(text="🔗 Добавить кнопку", callback_data="ad_button")],
        [InlineKeyboardButton(text="✅ Разместить рекламу", callback_data="ad_publish")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_home")],
    ])


def premium_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=v["label"], callback_data=f"premium_{k}")]
            for k, v in PRICES.items()]
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_keyboard(user_id: int) -> InlineKeyboardMarkup:
    with Database() as db:
        user_cats = db.get_user_categories(user_id)
    rows = []
    for cat in CATEGORIES:
        status = "✅" if cat in user_cats else "❌"
        rows.append([InlineKeyboardButton(text=f"{status} {cat}",
                                          callback_data=f"cat_toggle_{cat}")])
    rows.append([InlineKeyboardButton(text="💎 Получить ПРЕМИУМ", callback_data="menu_premium")])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_home")]
    ])