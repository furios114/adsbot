import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from keep_alive import keep_alive
from handlers import register_handlers

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    register_handlers(dp, bot)

    keep_alive()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())