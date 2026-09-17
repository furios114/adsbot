import asyncio
import logging

from database import init_pool, close_pool
from runtime import bot, dp

logging.basicConfig(level=logging.INFO)

import handlers  # noqa: E402,F401

logger = logging.getLogger(__name__)


async def main():
    # Инициализируем пул соединений с Postgres
    await init_pool()
    logger.info("Пул БД инициализирован")

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())