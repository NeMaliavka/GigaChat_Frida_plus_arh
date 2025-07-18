import logging
from datetime import datetime, timedelta
from typing import Union
from zoneinfo import ZoneInfo

from aiogram import types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from app.config import TEACHER_IDS
from app.services.bitrix_service import get_free_slots
from app.states.fsm_states import BookingFSM
# Убедитесь, что ваш форматтер поддерживает режим 'date_only'
from app.utils.formatters import format_date_russian

async def show_available_dates(event: Union[Message, CallbackQuery], state: FSMContext):
    """
    Получает слоты и отображает пользователю кнопки с выбором даты.
    """
    is_callback = isinstance(event, CallbackQuery)
    message_to_edit: Message

    # Определяем, редактировать сообщение или отправлять новое
    if is_callback:
        message_to_edit = event.message
        try:
            await message_to_edit.edit_text("Отлично! Загружаю доступное расписание...")
        except TelegramBadRequest:
            pass # Игнорируем ошибку, если текст не изменился
    else:
        user_message = event
        message_to_edit = await user_message.answer("Отлично! Загружаю доступное расписание...")

    try:
        portal_tz = ZoneInfo("Europe/Moscow")
        now = datetime.now(portal_tz)
        free_slots_by_date = await get_free_slots(from_date=now, to_date=now + timedelta(days=7), user_ids=TEACHER_IDS)

        if not free_slots_by_date:
            await message_to_edit.edit_text("К сожалению, на ближайшую неделю свободных окон нет.")
            if is_callback: await event.answer()
            return

        # Сохраняем полученные слоты в состояние FSM для дальнейшего использования
        await state.update_data(free_slots=free_slots_by_date)
        
        date_buttons = []
        for date_str in sorted(free_slots_by_date.keys()):
            # Превращаем строку 'YYYY-MM-DD' в объект даты
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            # Форматируем ее в нужный нам вид 'DD.MM.YYYY' без времени
            button_text = date_obj.strftime('%d.%m.%Y')
            
            date_buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"book_date:{date_str}"
            )])

        keyboard = InlineKeyboardMarkup(inline_keyboard=date_buttons)
        await message_to_edit.edit_text("Выберите удобный день:", reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Критическая ошибка при показе дат: {e}", exc_info=True)
        await message_to_edit.edit_text("Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if is_callback:
            await event.answer()

async def get_time_keyboard(state: FSMContext, selected_date: str) -> InlineKeyboardMarkup:
    """
    Создает и возвращает клавиатуру с доступными временными слотами для выбранной даты.
    """
    fsm_data = await state.get_data()
    slots_for_date = fsm_data.get('free_slots', {}).get(selected_date, [])
    unique_times = sorted(list(set(s['time'] for s in slots_for_date)))

    time_buttons = [
        InlineKeyboardButton(text=time_str, callback_data=f"book_time:{selected_date}T{time_str}")
        for time_str in unique_times
    ]

    # Группируем кнопки по 3 в ряд для компактности
    grouped_buttons = [time_buttons[i:i + 3] for i in range(0, len(time_buttons), 3)]
    
    # --- ИЗМЕНЕНИЕ 2: Делаем кнопку "Назад" более логичной ---
    # Теперь она будет явно возвращать к выбору даты.
    grouped_buttons.append([InlineKeyboardButton(text="⬅️ Назад к выбору дня", callback_data="back_to_dates")])
    
    return InlineKeyboardMarkup(inline_keyboard=grouped_buttons)
