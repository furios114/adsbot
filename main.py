import asyncio
import logging

from runtime import bot, dp
from parser.client import ParserClient

logging.basicConfig(level=logging.INFO)

import handlers  # noqa: E402,F401

logger = logging.getLogger(__name__)

parser_client = ParserClient(bot)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем парсер параллельно с ботом
    asyncio.create_task(parser_client.start())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())