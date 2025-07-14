# # import asyncio
# # import logging

# # from aiogram import Bot, Dispatcher
# # from aiogram.client.bot import DefaultBotProperties
# # from aiogram.enums import ParseMode

# # # ИСПРАВЛЕНО: Правильное имя переменной и пути импорта
# # from app.config import TELEGRAM_BOT_TOKEN
# # from app.handlers import common, sales_funnel, callback_handlers
# # from app.db.database import init_db

# # # Настройка логирования перенесена в config.py, здесь она не нужна
# # # logging.basicConfig(...)

# # async def main():
# #     """Основная функция для запуска бота."""
# #     logging.info("Инициализация базы данных...")
# #     await init_db()
# #     logging.info("База данных инициализирована.")

# #     bot = Bot(
# #         token=TELEGRAM_BOT_TOKEN, # ИСПРАВЛЕНО: Используем правильное имя
# #         default=DefaultBotProperties(parse_mode=ParseMode.HTML)
# #     )
# #     dp = Dispatcher()

# #     dp.include_router(common.router)
# #     dp.include_router(sales_funnel.router)
# #     dp.include_router(callback_handlers.router) 
# #     logging.info("Обработчики зарегистрированы.")

# #     logging.info("Бот запускается...")
# #     # Удаляем сессии бота перед запуском
# #     await bot.delete_webhook(drop_pending_updates=True)
# #     await dp.start_polling(bot)

# # if __name__ == "__main__":
# #     try:
# #         asyncio.run(main())
# #     except (KeyboardInterrupt, SystemExit):
# #         logging.info("Бот остановлен.")

# # app/main.py
# import asyncio
# import logging
# from aiogram import Bot, Dispatcher, F
# from aiogram.fsm.storage.memory import MemoryStorage
# from aiogram.client.bot import DefaultBotProperties
# from aiogram.enums import ParseMode

# # Импортируем конфигурацию
# from app.config import TELEGRAM_BOT_TOKEN, LOG_LEVEL

# # Импортируем наши роутеры из папки handlers
# from app.handlers import common, sales_funnel

# async def main():
#     """Главная функция для запуска бота."""
    
#     # Настраиваем логирование
#     logging.basicConfig(
#         level=LOG_LEVEL,
#         format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
#     )
#     logging.info("Запуск бота...")

#     # Инициализируем бота и диспетчер
#     # MemoryStorage - простое хранилище состояний FSM в оперативной памяти
#     # Для production лучше использовать RedisStorage
#     storage = MemoryStorage()
#     bot = Bot(
#         token=TELEGRAM_BOT_TOKEN, # ИСПРАВЛЕНО: Используем правильное имя
#         default=DefaultBotProperties(parse_mode=ParseMode.HTML)
#     )
#     dp = Dispatcher(storage=storage)

#     # --- РЕГИСТРАЦИЯ РОУТЕРОВ ---
#     # Порядок регистрации важен!
#     # Сначала регистрируем обработчики общих команд (например, /start).
#     dp.include_router(common.router)
#     # Затем регистрируем основной роутер со сценариями и обработкой текста.
#     dp.include_router(sales_funnel.router)

#     # Перед запуском polling удаляем все старые вебхуки
#     await bot.delete_webhook(drop_pending_updates=True)
#     # Запускаем polling
#     try:
#         await dp.start_polling(bot)
#     finally:
#         await bot.session.close()

# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except (KeyboardInterrupt, SystemExit):
#         logging.info("Бот остановлен.")
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties

# Импортируем конфигурацию
from app.config import TELEGRAM_BOT_TOKEN, LOG_LEVEL

# Импортируем наши роутеры из папки handlers
# ИСПРАВЛЕНО: Добавляем новый роутер для callback-запросов
from app.handlers import common, sales_funnel, callback_handlers
from app.db.database import init_db

from app.services.bitrix_service import check_b24_connection

async def main():
    """Главная функция для запуска бота."""
    
    # Настраиваем логирование
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.info("Запуск бота...")

    # Инициализация базы данных
    await init_db()
    # Проверяем соединение с Битрикс24 перед запуском основной логики бота
    logging.info("Проверка соединения с Битрикс24...")
    await check_b24_connection()

    # Инициализируем хранилище состояний
    storage = MemoryStorage()
    
    # Инициализация бота по новому стандарту aiogram 3.7.0+
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode="HTML")
    )
    
    # Инициализируем диспетчер
    dp = Dispatcher(storage=storage)

    # --- РЕГИСТРАЦИЯ РОУТЕРОВ ---
    # Порядок регистрации важен!
    dp.include_router(common.router)
    dp.include_router(sales_funnel.router)
    # ДОБАВЛЕНО: Регистрируем новый роутер для обработки кнопок
    dp.include_router(callback_handlers.router)
    logging.info("Роутеры успешно зарегистрированы.")

    # Перед запуском polling удаляем все старые вебхуки
    await bot.delete_webhook(drop_pending_updates=True)
    allowed_updates = dp.resolve_used_update_types()
    
    logging.info("Запуск бота...")
    try:
        # Передаем список разрешенных обновлений в start_polling
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await bot.session.close()
        logging.info("Сессия бота закрыта.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
    
#     # Запускаем polling
#     logging.info("Запуск бота...")
#     try:
#         await dp.start_polling(bot)
#     finally:
#         await bot.session.close()
#         logging.info("Сессия бота закрыта.")

# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except (KeyboardInterrupt, SystemExit):
#         logging.info("Бот остановлен.")
