# app/handlers/booking_handlers.py

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Union
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from app.states.fsm_states import BookingFSM
from app.utils.formatters import format_date_russian
from app.services.bitrix_service import get_free_slots, book_lesson
from app.db.database import get_or_create_user, add_trial_lesson
from app.config import TEACHER_IDS

router = Router()


async def start_booking_scenario(message: Message, state: FSMContext):
    """
    Запускает сценарий бронирования по текстовой команде от LLM.
    """
    logging.info(f"Запуск сценария бронирования для {message.from_user.id} из sales_funnel.")
    await state.clear()
    await _show_available_dates(message, state)


@router.callback_query(F.data == "start_booking")
async def handle_start_booking_callback(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие inline-кнопки "Начать бронирование" или "Назад к выбору дня".
    """
    await _show_available_dates(callback, state)


# --- ИСПРАВЛЕННАЯ ВЕРСИЯ ФУНКЦИИ ---
async def _show_available_dates(event: Union[Message, CallbackQuery], state: FSMContext):
    """
    Получает слоты и отображает пользователю кнопки с выбором даты.
    """
    is_callback = isinstance(event, CallbackQuery)
    message_to_edit: Message

    # Определяем, какое сообщение будем редактировать
    if is_callback:
        # Если это колбэк, редактируем сообщение, к которому привязана кнопка
        message_to_edit = event.message
        try:
            await message_to_edit.edit_text("Отлично! Загружаю доступное расписание...")
        except TelegramBadRequest:
            # Игнорируем ошибку, если текст не изменился
            pass
    else:
        # Если это текстовая команда, отправляем НОВОЕ сообщение и СОХРАНЯЕМ его
        user_message = event
        message_to_edit = await user_message.answer("Отлично! Загружаю доступное расписание...")

    # Вся дальнейшая работа идет с переменной message_to_edit
    try:
        portal_tz = ZoneInfo("Europe/Moscow")
        now = datetime.now(portal_tz)
        free_slots_by_date = await get_free_slots(from_date=now, to_date=now + timedelta(days=7), user_ids=TEACHER_IDS)

        if not free_slots_by_date:
            await message_to_edit.edit_text("К сожалению, на ближайшую неделю свободных окон нет.")
            if is_callback:
                await event.answer()
            return

        await state.update_data(free_slots=free_slots_by_date)
        date_buttons = [[InlineKeyboardButton(text=format_date_russian(datetime.strptime(date_str, '%Y-%m-%d'), 'full'), callback_data=f"book_date:{date_str}")] for date_str in sorted(free_slots_by_date.keys())]
        keyboard = InlineKeyboardMarkup(inline_keyboard=date_buttons)

        await state.set_state(BookingFSM.choosing_date)
        await message_to_edit.edit_text("Выберите удобный день:", reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Критическая ошибка при показе дат: {e}", exc_info=True)
        await message_to_edit.edit_text("Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if is_callback:
            await event.answer()


# --- Остальные обработчики остаются без изменений ---
# (Ваш код для них уже корректен)

@router.callback_query(BookingFSM.choosing_date, F.data.startswith("book_date:"))
async def handle_date_selection(callback: types.CallbackQuery, state: FSMContext):
    # ... ваш код для выбора даты ...
    selected_date = callback.data.split(":")[1]
    fsm_data = await state.get_data()
    slots_for_date = fsm_data.get('free_slots', {}).get(selected_date, [])
    unique_times = sorted(list(set(s['time'] for s in slots_for_date)))
    time_buttons = [
        InlineKeyboardButton(text=time_str, callback_data=f"book_time:{selected_date}T{time_str}")
        for time_str in unique_times
    ]
    grouped_buttons = [time_buttons[i:i + 3] for i in range(0, len(time_buttons), 3)]
    grouped_buttons.append([InlineKeyboardButton(text="⬅️ Назад к выбору дня", callback_data="start_booking")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=grouped_buttons)
    formatted_date = format_date_russian(datetime.strptime(selected_date, '%Y-%m-%d'), 'full')
    await callback.message.edit_text(f"Вы выбрали {formatted_date}.\nТеперь выберите удобное время:", reply_markup=keyboard)
    await state.set_state(BookingFSM.choosing_time)
    await callback.answer()


@router.callback_query(BookingFSM.choosing_time, F.data.startswith("book_time:"))
async def handle_time_selection(callback: types.CallbackQuery, state: FSMContext):
    # ... ваш код для выбора времени и бронирования ...
    await callback.message.edit_text("Секундочку, сверяюсь с расписанием...")
    datetime_str = callback.data.split(":", 1)[1]
    start_time = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M').replace(tzinfo=ZoneInfo("Europe/Moscow"))
    fsm_data = await state.get_data()
    user_db = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    client_data = user_db.user_data or {}
    client_data['username'] = callback.from_user.username
    selected_date_str = start_time.strftime('%Y-%m-%d')
    selected_time_str = start_time.strftime('%H:%M')
    all_slots_for_date = fsm_data.get('free_slots', {}).get(selected_date_str, [])
    slot_info_list = [s for s in all_slots_for_date if s['time'] == selected_time_str]
    if not slot_info_list:
        await callback.message.edit_text("😔 Ой, кажется, это время только что полностью заняли. Пожалуйста, выберите другое.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Выбрать другой день", callback_data="start_booking")]]))
        await callback.answer()
        return
    available_teacher_ids = slot_info_list[0]['user_ids']
    created_task_id, created_event_id, assigned_teacher_name = None, None, None
    for teacher_id in available_teacher_ids:
        task_id, event_id, teacher_name = await book_lesson(user_id=teacher_id, start_time=start_time, duration_minutes=60, client_data=client_data)
        if task_id and event_id:
            created_task_id, created_event_id, assigned_teacher_name = task_id, event_id, teacher_name
            break
    if created_task_id and created_event_id:
        confirmation_date = format_date_russian(start_time, 'short')
        await add_trial_lesson(user_id=user_db.id, task_id=created_task_id, event_id=created_event_id, scheduled_at=start_time)
        await callback.message.edit_text(f"Отлично! ✅\n\nВы успешно записаны на пробный урок {confirmation_date}. Вся информация передана вашему преподавателю: {assigned_teacher_name}. До встречи!", reply_markup=None)
        await state.clear()
    else:
        await callback.message.edit_text("😔 Ой, кажется, это время только что полностью заняли. Пожалуйста, выберите другое.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Выбрать другой день", callback_data="start_booking")]]))
    await callback.answer()

