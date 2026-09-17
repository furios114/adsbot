"""
Одноразовый скрипт для входа в Telegram-аккаунт парсера.
Запусти ОДИН РАЗ на сервере: python login.py
"""
import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession

from config import API_ID, API_HASH

SESSION_FILE = "parser_session.txt"


async def main():
    if API_ID == 0 or not API_HASH or API_HASH.startswith("PASTE"):
        print("❌ Заполни API_ID и API_HASH в config.py")
        return

    print("=" * 50)
    print("ВХОД В TELEGRAM-АККАУНТ ПАРСЕРА")
    print("=" * 50)
    print("Используй ОТДЕЛЬНЫЙ аккаунт, не свой личный!")
    print()

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()

    me = await client.get_me()
    print()
    print(f"✅ Вход выполнен: @{me.username or me.id} ({me.first_name})")

    session_string = client.session.save()
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(session_string)

    print(f"✅ Сессия сохранена в {SESSION_FILE}")
    print("Теперь можно запускать бота: systemctl restart adsbot")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())