import asyncio
import logging

from runtime import bot, dp

logging.basicConfig(level=logging.INFO)

import handlers  # noqa: E402,F401  — регистрирует хендлеры на dp


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())