import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

# ИСПРАВЛЕНО: Правильное имя переменной и пути импорта
from app.config import TELEGRAM_BOT_TOKEN
from app.handlers import common, sales_funnel, callback_handlers
from app.db.database import init_db

# Настройка логирования перенесена в config.py, здесь она не нужна
# logging.basicConfig(...)

async def main():
    """Основная функция для запуска бота."""
    logging.info("Инициализация базы данных...")
    await init_db()
    logging.info("База данных инициализирована.")

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN, # ИСПРАВЛЕНО: Используем правильное имя
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(common.router)
    dp.include_router(sales_funnel.router)
    dp.include_router(callback_handlers.router) 
    logging.info("Обработчики зарегистрированы.")

    logging.info("Бот запускается...")
    # Удаляем сессии бота перед запуском
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")

