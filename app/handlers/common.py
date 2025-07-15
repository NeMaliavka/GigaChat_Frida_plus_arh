# app/handlers/common.py
import logging
from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

# Импортируем нужные функции из соседних модулей
from app.db.database import get_or_create_user
# Важно: импортируем функцию запуска FSM, чтобы не дублировать код
from app.handlers.onboarding_handlers import start_fsm_scenario

router = Router()

@router.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    """
    Обрабатывает команду /start.
    Проверяет, новый ли это пользователь, и в зависимости от этого
    либо запускает сценарий знакомства, либо приветствует по имени.
    """
    # Сбрасываем любое предыдущее состояние на случай, если пользователь
    # перезапустил бота в середине другого сценария
    await state.clear()

    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    logging.info(f"Пользователь {user.telegram_id} запустил команду /start. Статус онбординга: {user.onboarding_completed}")

    # Проверяем, проходил ли пользователь онбординг и есть ли у нас его имя
    if user.onboarding_completed and user.user_data and 'parent_name' in user.user_data:
        parent_name = user.user_data.get('parent_name', 'Гость')
        # Капитализируем каждое слово в имени/отчестве для вежливого обращения
        capitalized_name = " ".join(word.capitalize() for word in parent_name.split())
        
        await message.answer(
            f"С возвращением, {capitalized_name}! Рад вас снова видеть.\n\n"
            "Чем могу помочь сегодня?"
        )
    else:
        # Если пользователь новый или не закончил онбординг,
        # запускаем стандартный сценарий знакомства.
        await start_fsm_scenario(message, state)

