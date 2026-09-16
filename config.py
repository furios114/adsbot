import os

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8961329814:AAGmj_OW6YyalGLz_n_hlXb-dcZ4Sd31P8E"
ADMIN_IDS = [8678187296, 5973645939]

TON_ADDRESS = "UQDVW_nBIOY-xTEJmeXgjNMU-TUYdpvfUiyxBk3CsAVQsq0n"
TON_API_KEY = os.getenv("TON_API_KEY") or "dd0a506a287a6c121952383149a8233aa8eb66094e6616b5789d8911d1750c78"

SUPPORT_URL = "https://t.me/Artes_design"
TON_RATE_RUB = 200

PRICES = {
    "1m":  {"price": 890, "months": 1,  "label": "1 месяц — 890₽"},
    "3m":  {"price": 680, "months": 3,  "label": "3 месяца — 680₽/мес 🎁"},
    "6m":  {"price": 590, "months": 6,  "label": "6 месяцев — 590₽/мес 👍 ХИТ"},
    "12m": {"price": 530, "months": 12, "label": "12 месяцев — 530₽/мес 💰 ВЫГОДНО"},
}

CATEGORIES = [
    "Покупка рекламы",
    "Покупка ОП/приветки",
    "Покупка трафика",
    "Поиск менеджеров",
]

ORDER_CATEGORIES = {
    "📢 Реклама": "Покупка рекламы",
    "📄 ОП/приветки": "Покупка ОП/приветки",
    "🚀 Трафик": "Покупка трафика",
    "👨‍💼 Менеджеры": "Поиск менеджеров",
}

AD_PRICE_RUB = 590