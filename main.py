import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()

from database import init_pool, close_pool
from runtime import bot, dp
from parser.client import ParserClient
from parser.dispatcher import broadcast_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)

import handlers  # noqa: E402,F401

logger = logging.getLogger(__name__)


async def main():
    await init_pool()
    logger.info("Пул БД инициализирован")

    await bot.delete_webhook(drop_pending_updates=True)

    parser = ParserClient(bot)
    asyncio.create_task(parser.start())

    asyncio.create_task(broadcast_worker(bot, interval=600))

    try:
        await dp.start_polling(bot)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())