# app/handlers/check_booking_handlers.py

import logging
from aiogram import Router, types

from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
# Используем get_all_active_lessons вместо get_active_lesson
from app.db.database import get_or_create_user, get_all_active_lessons
from app.utils.formatters import format_date_russian
from app.utils.text_tools import inflect_name

router = Router()

def get_check_booking_keyboard():
    """Создает клавиатуру для сообщения о найденных записях."""
    builder = InlineKeyboardBuilder()
    builder.button(text="↪️ Перенести занятие", callback_data="reschedule_booking")
    # --- ДОБАВЛЕНА КНОПКА ОТМЕНЫ ---
    builder.button(text="❌ Отменить занятие", callback_data="cancellation_request")
    builder.button(text="⬅️ Вернуться в главное меню", callback_data="main_menu")
    # Располагаем кнопки в один столбец для лучшей читаемости
    builder.adjust(1)
    return builder.as_markup()

def get_no_lessons_keyboard():
    """Создает клавиатуру для случая, когда нет уроков."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, записаться", callback_data="start_booking")
    builder.button(text="⬅️ Вернуться в главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def start_check_booking_flow(message: types.Message, state: FSMContext, user_id: int, username: str | None):
    """
    Начинает процесс проверки записи: ищет ВСЕ активные уроки и сообщает о них.
    """
    await state.clear()
    user = await get_or_create_user(user_id, username) 
    active_lessons = await get_all_active_lessons(user.id)
    
    if not active_lessons:
        await message.answer(
            "Я проверил, но пока не нашел у вас запланированных уроков. "
            "Может, запишемся на пробное занятие?",
            reply_markup=get_no_lessons_keyboard()
        )
        return
    child_name_raw = user.user_data.get('child_name', 'вашего ребенка')
    child_name = inflect_name(child_name_raw, case='gent')
    keyboard = get_check_booking_keyboard()

    if len(active_lessons) == 1:
        lesson = active_lessons[0]
        lesson_time_str = format_date_russian(lesson.scheduled_at, 'full')    
        await message.answer(
            f"Да, конечно! Нашел вашу запись. ✅\n\n"
            f"Пробный урок для {child_name} запланирован на {lesson_time_str}.",
            reply_markup=keyboard
        )
    else:
        response_text = "Да, у вас есть несколько активных записей:\n"
        for i, lesson in enumerate(active_lessons, 1):
            lesson_time_str = format_date_russian(lesson.scheduled_at, 'full')           
            response_text += f"\n{i}. Пробный урок для {child_name} на {lesson_time_str}"
        
        await message.answer(response_text,
            reply_markup=keyboard)