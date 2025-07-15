# main.py

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties

# --- 1. Импорт конфигурации и сервисов ---
from app.config import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from app.db.database import init_db
from app.services.bitrix_service import check_b24_connection

# --- 2. Корректный импорт всех роутеров ---
from app.handlers import (
    admin_handlers,
    common,
    sales_funnel,
    onboarding_handlers,
    booking_handlers,
    waitlist_handlers,
    callback_handlers,
    cancellation_handlers
)


async def main():
    """Главная функция для запуска бота."""
    
    # --- 3. Инициализация ---
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.info("Запуск бота...")
    
    await init_db()
    logging.info("База данных успешно инициализирована.")
    
    logging.info("Проверка соединения с Битрикс24...")
    await check_b24_connection()
    
    storage = MemoryStorage()
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=storage)

    # --- 4. РЕГИСТРАЦИЯ РОУТЕРОВ В ПРАВИЛЬНОМ ПОРЯДКЕ ---
    # Порядок регистрации критически важен для корректной работы!
    
    # Первыми регистрируем админские команды, чтобы они имели наивысший приоритет.
    dp.include_router(admin_handlers.router)
    
    # Затем - общие команды (например, /start), которые должны работать из любого состояния.
    dp.include_router(common.router)
    
    # Далее - все обработчики FSM-сценариев и колбэков.
    # Их порядок между собой не так важен, т.к. они срабатывают по разным фильтрам.
    dp.include_router(booking_handlers.router)
    dp.include_router(waitlist_handlers.router)
    dp.include_router(cancellation_handlers.router)
    dp.include_router(onboarding_handlers.router)
    dp.include_router(callback_handlers.router)
    
    # В последнюю очередь регистрируем "catch-all" диспетчер для всех остальных текстовых сообщений.
    dp.include_router(sales_funnel.router)
    
    logging.info("Все роутеры успешно зарегистрированы.")

    # --- 5. Запуск бота ---
    # Удаляем вебхук и получаем список обновлений, которые бот будет слушать.
    await bot.delete_webhook(drop_pending_updates=True)
    allowed_updates = dp.resolve_used_update_types()
    logging.info(f"Бот будет принимать следующие типы обновлений: {allowed_updates}")
    
    try:
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await bot.session.close()
        logging.info("Сессия бота закрыта.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")

