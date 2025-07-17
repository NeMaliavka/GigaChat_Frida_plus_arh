# app/handlers/check_booking_handlers.py
import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from app.db.database import get_or_create_user, get_active_lesson
from app.utils.formatters import format_date_russian

router = Router()

async def start_check_booking_flow(message: types.Message, state: FSMContext):
    """
    Начинает процесс проверки записи: ищет активный урок и сообщает о нем.
    """
    await state.clear()
    logging.info(f"Пользователь {message.from_user.id} запросил проверку записи.")
    
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    active_lesson = await get_active_lesson(user.id)
    
    if active_lesson and active_lesson.scheduled_at:
        # Если урок найден, форматируем дату и сообщаем пользователю
        lesson_time_str = format_date_russian(active_lesson.scheduled_at, 'short')
        await message.answer(
            f"Да, конечно! Нашел вашу запись. ✅\n\n"
            f"Пробный урок запланирован на {lesson_time_str}. Ждем вас!"
        )
    else:
        # Если уроков нет
        await message.answer(
            "Я проверил, но пока не нашел у вас запланированных уроков. "
            "Может, запишемся на пробное занятие?"
        )

