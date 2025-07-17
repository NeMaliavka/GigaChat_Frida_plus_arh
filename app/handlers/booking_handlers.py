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
from app.db.database import get_or_create_user, add_trial_lesson, get_active_lesson
from app.config import TEACHER_IDS

from app.handlers import reschedule_handlers

from app.handlers.utils.booking_utils import show_available_dates, get_time_keyboard

router = Router()

async def start_booking_scenario(message: Message, state: FSMContext):
    """
    Запускает сценарий бронирования по текстовой команде от LLM.
    """
    logging.info(f"Запуск сценария бронирования для {message.from_user.id} из sales_funnel.")
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    active_lesson = await get_active_lesson(user.id)
    
    # Если найден активный урок, предлагаем варианты вместо новой записи
    if active_lesson and active_lesson.scheduled_at:
        lesson_time_str = format_date_russian(active_lesson.scheduled_at, 'short')
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗓️ Да, перенести запись", callback_data="initiate_reschedule")],
            [InlineKeyboardButton(text="👨‍👧‍👦 Записать другого ребенка", callback_data="start_booking_force")],
            [InlineKeyboardButton(text="✅ Нет, спасибо", callback_data="cancel_action")]
        ])
        
        await message.answer(
            f"⚠️ Я вижу, у вас уже есть активная запись!\n\n"
            f"Пробный урок запланирован на **{lesson_time_str}**.\n\n"
            f"Хотите **перенести** это занятие или **записать другого ребенка**?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return
    await state.clear()
    await show_available_dates(message, state)
    # Устанавливаем состояние ПОСЛЕ вызова утилиты
    await state.set_state(BookingFSM.choosing_date)


@router.callback_query(F.data == "start_booking")
async def handle_start_booking_callback(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие inline-кнопки "Начать бронирование" или "Назад к выбору дня".
    """
    await show_available_dates(callback, state)
    # Устанавливаем состояние ПОСЛЕ вызова утилиты
    await state.set_state(BookingFSM.choosing_date)


# async def _show_available_dates(event: Union[Message, CallbackQuery], state: FSMContext):
#     """
#     Получает слоты и отображает пользователю кнопки с выбором даты.
#     ИСПРАВЛЕНО: Эта функция больше не управляет состоянием FSM.
#     """
#     is_callback = isinstance(event, CallbackQuery)
#     message_to_edit: Message

#     if is_callback:
#         message_to_edit = event.message
#         try:
#             await message_to_edit.edit_text("Отлично! Загружаю доступное расписание...")
#         except TelegramBadRequest:
#             pass  # Игнорируем ошибку, если текст не изменился
#     else:
#         user_message = event
#         message_to_edit = await user_message.answer("Отлично! Загружаю доступное расписание...")

#     try:
#         portal_tz = ZoneInfo("Europe/Moscow")
#         now = datetime.now(portal_tz)
#         free_slots_by_date = await get_free_slots(from_date=now, to_date=now + timedelta(days=7), user_ids=TEACHER_IDS)

#         if not free_slots_by_date:
#             await message_to_edit.edit_text("К сожалению, на ближайшую неделю свободных окон нет.")
#             if is_callback:
#                 await event.answer()
#             return

#         await state.update_data(free_slots=free_slots_by_date)

#         date_buttons = [
#             [InlineKeyboardButton(text=format_date_russian(datetime.strptime(date_str, '%Y-%m-%d'), 'full'), callback_data=f"book_date:{date_str}")]
#             for date_str in sorted(free_slots_by_date.keys())
#         ]
#         keyboard = InlineKeyboardMarkup(inline_keyboard=date_buttons)

#         # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Эта строка была ошибкой и удалена отсюда
#         # await state.set_state(BookingFSM.choosing_date)

#         await message_to_edit.edit_text("Выберите удобный день:", reply_markup=keyboard)

#     except Exception as e:
#         logging.error(f"Критическая ошибка при показе дат: {e}", exc_info=True)
#         await message_to_edit.edit_text("Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")
#     finally:
#         if is_callback:
#             await event.answer()


# async def _get_time_keyboard(state: FSMContext, selected_date: str) -> InlineKeyboardMarkup:
#     """
#     Создает и возвращает клавиатуру с доступными временными слотами для выбранной даты.
#     """
#     fsm_data = await state.get_data()
#     slots_for_date = fsm_data.get('free_slots', {}).get(selected_date, [])
#     unique_times = sorted(list(set(s['time'] for s in slots_for_date)))

#     time_buttons = [
#         InlineKeyboardButton(text=time_str, callback_data=f"book_time:{selected_date}T{time_str}")
#         for time_str in unique_times
#     ]

#     grouped_buttons = [time_buttons[i:i + 3] for i in range(0, len(time_buttons), 3)]
#     grouped_buttons.append([InlineKeyboardButton(text="⬅️ Назад к выбору дня", callback_data="start_booking")])

#     return InlineKeyboardMarkup(inline_keyboard=grouped_buttons)


@router.callback_query(BookingFSM.choosing_date, F.data.startswith("book_date:"))
async def handle_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор даты и показывает доступное время.
    """
    selected_date = callback.data.split(":")[1]
    
    # Используем общую утилиту вместо дублирования кода
    keyboard = await get_time_keyboard(state, selected_date)
    
    formatted_date = format_date_russian(datetime.strptime(selected_date, '%Y-%m-%d'), 'full')
    await callback.message.edit_text(f"Вы выбрали {formatted_date}.\nТеперь выберите удобное время:", reply_markup=keyboard)
    
    # Устанавливаем следующее состояние
    await state.set_state(BookingFSM.choosing_time)
    await callback.answer()


@router.callback_query(BookingFSM.choosing_time, F.data.startswith("book_time:"))
async def handle_time_selection(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор времени, бронирует урок и сохраняет результат.
    """
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
        await callback.message.edit_text(
            "😔 Ой, кажется, это время только что полностью заняли. Пожалуйста, выберите другое.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Выбрать другой день", callback_data="start_booking")]])
        )
        await callback.answer()
        return

    available_teacher_ids = slot_info_list[0]['user_ids']
    created_task_id, created_event_id, assigned_teacher_name = None, None, None
    assigned_teacher_id = None

    for teacher_id in available_teacher_ids:
        task_id, event_id, teacher_name = await book_lesson(user_id=teacher_id, start_time=start_time, duration_minutes=60, client_data=client_data)
        if task_id and event_id:
            created_task_id, created_event_id, assigned_teacher_name = task_id, event_id, teacher_name
            assigned_teacher_id = teacher_id
            break

    if created_task_id and created_event_id:
        confirmation_date = format_date_russian(start_time, 'short')
        await add_trial_lesson(
            user_id=user_db.id,
            task_id=created_task_id,
            event_id=created_event_id,
            teacher_id=assigned_teacher_id,
            scheduled_at=start_time
        )
        await callback.message.edit_text(
            f"Отлично! ✅\n\nВы успешно записаны на пробный урок {confirmation_date}. Вся информация передана вашему преподавателю: {assigned_teacher_name}. До встречи!",
            reply_markup=None
        )
        await state.clear()
    else:
        await callback.message.edit_text(
            "😔 Ой, кажется, это время только что полностью заняли. Пожалуйста, выберите другое.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Выбрать другой день", callback_data="start_booking")]])
        )
    
    await callback.answer()
@router.callback_query(F.data == "start_booking_force")
async def handle_force_start_booking(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает кнопку "Записать другого ребенка".
    Запускает стандартный сценарий бронирования, игнорируя проверку.
    """
    await state.clear()
    # Запускаем оригинальную логику показа дат
    await show_available_dates(callback, state)
    await state.set_state(BookingFSM.choosing_date)
    await callback.answer()

@router.callback_query(F.data == "initiate_reschedule")
async def handle_initiate_reschedule_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Перенаправляет пользователя в сценарий переноса записи.
    """
    await callback.message.edit_text("Понял. Давайте подберем новое время. Запускаю процесс переноса...")
    # Вызываем существующую функцию из обработчика переносов
    await reschedule_handlers.initiate_reschedule_from_text(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "cancel_action")
async def handle_cancel_action(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает отмену действия (кнопка "Нет, спасибо").
    """
    await callback.message.edit_text("Хорошо! Если что-то понадобится — просто напишите мне.", reply_markup=None)
    await state.clear()
    await callback.answer()