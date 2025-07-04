from aiogram import Router, types
from aiogram.filters import CommandStart

from app.core.template_service import find_template, choose_variant
from app.db.database import save_history, load_history

router = Router()

@router.message(CommandStart())
async def handle_start(message: types.Message):
    """Обработчик команды /start."""
    user_id = str(message.from_user.id)
    
    # Сохраняем команду пользователя в историю
    await save_history(user_id, "user", message.text)
    
    # Загружаем историю, чтобы избежать повторений
    history = await load_history(user_id)
    
    # Ищем шаблон для приветствия
    greeting_template = find_template("приветствие")
    if greeting_template:
        response_text = choose_variant(greeting_template, history)
    else:
        response_text = "Здравствуйте! Я ИИ-ассистент школы No Bugs. Чем могу помочь?"
        
    await message.answer(response_text)
    await save_history(user_id, "assistant", response_text)

