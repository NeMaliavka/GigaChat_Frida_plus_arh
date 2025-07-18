# app/handlers/check_booking_handlers.py

import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext

# Используем get_all_active_lessons вместо get_active_lesson
from app.db.database import get_or_create_user, get_all_active_lessons
from app.utils.formatters import format_date_russian

router = Router()

async def start_check_booking_flow(message: types.Message, state: FSMContext):
    """
    Начинает процесс проверки записи: ищет ВСЕ активные уроки и сообщает о них.
    """
    await state.clear()
    logging.info(f"Пользователь {message.from_user.id} запросил проверку записи.")
    
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    active_lessons = await get_all_active_lessons(user.id) # <-- Ключевое изменение

    if not active_lessons:
        await message.answer(
            "Я проверил, но пока не нашел у вас запланированных уроков. "
            "Может, запишемся на пробное занятие?"
        )
        return
    child_name = user.user_data.get('child_name', 'вашего ребенка') if user.user_data else 'вашего ребенка'
        
    if len(active_lessons) == 1:
        lesson = active_lessons[0]
        lesson_time_str = format_date_russian(lesson.scheduled_at, 'full')    
        await message.answer(
            f"Да, конечно! Нашел вашу запись. ✅\n\n"
            f"Пробный урок для {child_name} запланирован на {lesson_time_str}."
        )
    else:
        response_text = "Да, у вас есть несколько активных записей:\n"
        for i, lesson in enumerate(active_lessons, 1):
            lesson_time_str = format_date_russian(lesson.scheduled_at, 'full')           
            response_text += f"\n{i}. Пробный урок для {child_name} на {lesson_time_str}"
        
        await message.answer(response_text)