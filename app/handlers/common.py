import logging
from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

# ВАЖНО: Импортируем наши сервисы для работы с шаблонами
from app.core.template_service import find_template, choose_variant
from app.db.database import get_or_create_user

router = Router()

@router.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    """
    Универсальный обработчик команды /start.
    Берет приветствие из внешнего файла шаблонов.
    """
    await state.clear()
    await get_or_create_user(message.from_user.id, message.from_user.username)
    
    # Ищем шаблон по зарезервированному ключу "start_greeting"
    _key, template_variants = find_template("start_greeting")
    
    # Выбираем случайный вариант приветствия
    welcome_text = choose_variant(template_variants) if template_variants else "Здравствуйте!"

    await message.answer(welcome_text)
    logging.info(f"Пользователь {message.from_user.id} нажал /start.")
