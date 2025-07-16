# app/handlers/reschedule_handlers.py

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.database import get_or_create_user, get_active_lesson, update_trial_lesson_time
from app.states.fsm_states import BookingFSM
from app.handlers.booking_handlers import _show_available_dates, _get_time_keyboard
from app.services.bitrix_service import reschedule_booking
from app.utils.formatters import format_date_russian

router = Router()

async def initiate_reschedule_from_text(message: types.Message, state: FSMContext):
    """Инициирует сценарий переноса из текстового сообщения."""
    logging.info(f"Запрос на перенос от {message.from_user.id} через текст. Предлагаем кнопку.")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перенести запись", callback_data="initiate_reschedule")]
    ])
    await message.answer(
        "Вы хотите перенести существующую запись на другое время?",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "initiate_reschedule")
async def start_reschedule_flow(callback: types.CallbackQuery, state: FSMContext):
    """Находит активный урок, сохраняет данные и запрашивает подтверждение."""
    await state.clear()
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    active_lesson = await get_active_lesson(user.id)

    if not active_lesson:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Да, записаться", callback_data="start_booking")]])
        await callback.message.edit_text("Я проверил, но у вас нет запланированных уроков для переноса.\n\nДавайте я помогу вам записаться на новый?", reply_markup=keyboard)
        await callback.answer()
        return
    # Убеждаемся, что scheduled_at - это действительно объект datetime, перед тем как использовать его методы.
    if not isinstance(active_lesson.scheduled_at, datetime):
        logging.error(f"Критическая ошибка: у активного урока {active_lesson.id} отсутствует дата. Перенос невозможен.")
        await callback.message.edit_text("Произошла внутренняя ошибка. Не удалось определить дату вашего урока. Пожалуйста, свяжитесь с поддержкой.")
        await callback.answer()
        return
    
    await state.update_data(
        lesson_to_reschedule_id=active_lesson.id,
        task_id=active_lesson.task_id,
        event_id=active_lesson.event_id,
        teacher_id=active_lesson.teacher_id,
        old_start_time=active_lesson.scheduled_at.isoformat()
    )

    lesson_time_str = active_lesson.scheduled_at.strftime("%d.%m.%Y в %H:%M")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, выбрать новое время", callback_data="confirm_reschedule")],
        [InlineKeyboardButton(text="Нет, я передумал(а)", callback_data="cancel_action")]
    ])
    await callback.message.edit_text(f"Ваш урок запланирован на {lesson_time_str}.\n\nВы хотите перенести его на другое время?", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "confirm_reschedule")
async def confirm_reschedule(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждает перенос и запускает показ свободных дат."""
    await callback.message.edit_text("Отлично! Давайте подберем новое время.")
    await state.set_state(BookingFSM.rescheduling_in_progress)
    await _show_available_dates(callback, state)
    await callback.answer()

@router.callback_query(BookingFSM.rescheduling_in_progress, F.data.startswith("book_date:"))
async def handle_reschedule_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор ДАТЫ в сценарии переноса, СОХРАНЯЯ ПРАВИЛЬНОЕ СОСТОЯНИЕ."""
    selected_date = callback.data.split(":")[1]
    await state.update_data(selected_date=selected_date)
    keyboard = await _get_time_keyboard(state, selected_date)
    await callback.message.edit_text(f"Вы выбрали {selected_date}. Теперь выберите удобное время:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(BookingFSM.rescheduling_in_progress, F.data.startswith("book_time:"))
async def handle_reschedule_time_selection(callback: types.CallbackQuery, state: FSMContext):
    """Ловит финальный выбор ВРЕМЕНИ, вызывает сервис ПЕРЕНОСА и завершает процесс."""
    await callback.message.edit_text("Минутку, переношу вашу запись на новое время...")

    fsm_data = await state.get_data()
    user_db = await get_or_create_user(callback.from_user.id, callback.from_user.username)

    datetime_str = callback.data.split(":", 1)[1]
    new_start_time = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M').replace(tzinfo=ZoneInfo("Europe/Moscow"))
    old_start_time = datetime.fromisoformat(fsm_data.get("old_start_time"))

    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
    # Получаем данные из JSON-поля user_data. Имя ребёнка там уже есть.
    client_data = user_db.user_data or {}
    # Просто добавляем актуальный username
    client_data['username'] = callback.from_user.username
    # Строка client_data['child_name'] = user_db.child_name была ошибочной и УДАЛЕНА.
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    success = await reschedule_booking(
        task_id=fsm_data.get("task_id"),
        event_id=fsm_data.get("event_id"),
        old_start_time=old_start_time,
        new_start_time=new_start_time,
        teacher_id=fsm_data.get("teacher_id"),
        client_data=client_data
    )

    if success:
        await update_trial_lesson_time(fsm_data.get("lesson_to_reschedule_id"), new_start_time)
        new_time_str = format_date_russian(new_start_time, 'short')
        await callback.message.edit_text(f"✅ Готово! Ваша запись успешно перенесена на {new_time_str}.")
    else:
        await callback.message.edit_text("😔 К сожалению, не удалось перенести запись. Слот мог быть занят. Попробуйте снова или свяжитесь с менеджером.")

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_action")
async def cancel_any_action(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет любой текущий процесс."""
    await state.clear()
    await callback.message.edit_text("Хорошо, я отменил операцию. Если что-то понадобится — обращайтесь!")
    await callback.answer()
