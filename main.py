import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import TOKEN
from handlers.handlers_logic import register_handlers

# 🫀 Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 🫀 Инициализация и запуск бота
async def main():
    logger.info("Запуск бота...")

    # 🔑 Создание экземпляра бота с токеном и HTML-парсингом
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # 🧠 Хранилище состояний в оперативной памяти
    storage = MemoryStorage()

    # 🫂 Диспетчер событий
    dp = Dispatcher(storage=storage)

    # 🔌 Регистрация всех хендлеров
    register_handlers(dp)

    # 🚀 Запуск поллинга
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную")
