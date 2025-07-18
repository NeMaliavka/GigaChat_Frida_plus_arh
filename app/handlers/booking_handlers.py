# app/handlers/booking_handlers.py

import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.database import get_or_create_user, add_trial_lesson, get_all_active_lessons
from app.states.fsm_states import BookingFSM
from app.services.bitrix_service import book_lesson
from app.utils.formatters import format_date_russian, get_user_data_summary
from app.handlers.utils.booking_utils import show_available_dates, get_time_keyboard
from app.handlers import reschedule_handlers, onboarding_handlers
from app.core.admin_notifications import notify_admin_of_request

from app.utils.text_tools import inflect_name
from app.handlers.utils.keyboards import get_faq_menu

router = Router()

async def start_booking_scenario(message: types.Message, state: FSMContext):
    """
    Запускает сценарий бронирования, показывая доступные даты.
    """
    await state.set_state(BookingFSM.choosing_date)
    await show_available_dates(message, state)

def get_duplicate_booking_keyboard():
    """Создает клавиатуру для сообщения о найденном дубликате записи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗓️ Посмотреть мои записи", callback_data="check_booking")
    builder.button(text="👨‍👧‍👦 Добавить второго ребенка", callback_data="add_second_child")
    builder.button(text="⬅️ Вернуться в главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- ФУНКЦИЯ ДЛЯ КЛАВИАТУРЫ ---
def get_add_second_child_keyboard():
    """Создает клавиатуру для сценария добавления второго ребенка."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, отлично!", callback_data="add_second_child_confirm")
    builder.button(text="👩‍💼 Нужен менеджер", callback_data="add_second_child_manager")
    builder.button(text="⬅️ Вернуться в главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_final_booking_keyboard():
    """Создает клавиатуру для сообщения об успешной записи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗓️ Посмотреть мои записи", callback_data="check_booking")
    builder.button(text="⬅️ Вернуться в главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- НОВАЯ ФУНКЦИЯ ДЛЯ FAQ КЛАВИАТУРЫ (чтобы не было лишних импортов) ---
# def get_faq_menu_keyboard():
#     """Возвращает меню с частыми вопросами."""
#     builder = InlineKeyboardBuilder()
#     builder.button(text="💰 Узнать цены", callback_data="faq_price")
#     builder.button(text="📚 О программе курса", callback_data="faq_structure")
#     builder.button(text="🏫 В чем разница между курсами?", callback_data="faq_difference")
#     builder.button(text="⬅️ Назад в главное меню", callback_data="main_menu")
#     builder.adjust(1)
#     return builder.as_markup()


@router.callback_query(F.data == "start_booking")
async def handle_start_booking_callback(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на inline-кнопку "Да, записаться".
    """
    await callback.message.edit_text("Отлично! Давайте выберем удобный день для урока.")
    await start_booking_scenario(callback.message, state)
    await callback.answer()


@router.callback_query(BookingFSM.choosing_date, F.data.startswith("book_date:"))
async def handle_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор даты, показывает доступное время и ПЕРЕКЛЮЧАЕТ СОСТОЯНИЕ.
    """
    selected_date = callback.data.split(":")[1]
    logging.info(f"Пользователь {callback.from_user.id} выбрал дату: {selected_date}")
    await state.update_data(selected_date=selected_date)
    await state.set_state(BookingFSM.choosing_time)
    keyboard = await get_time_keyboard(state, selected_date)
    await callback.message.edit_text(f"Вы выбрали {selected_date}. Теперь выберите удобное время:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BookingFSM.choosing_time, F.data == "back_to_dates")
async def handle_back_to_dates_callback(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Назад к выбору дня".
    """
    logging.info(f"Пользователь {callback.from_user.id} вернулся к выбору даты.")
    await start_booking_scenario(callback.message, state)
    await callback.answer()


@router.callback_query(BookingFSM.choosing_time, F.data.startswith("book_time:"))
async def handle_time_selection(callback: types.CallbackQuery, state: FSMContext):
    """
    Ловит финальный выбор времени, проверяет на дубли, вызывает сервис бронирования и завершает FSM.
    """
    fsm_data = await state.get_data()
    user_db = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    
    # --- ДОБАВЛЕНА ПРОВЕРКА НА СУЩЕСТВУЮЩУЮ ЗАПИСЬ ---
    existing_lessons = await get_all_active_lessons(user_db.id)
    if existing_lessons:
        await callback.message.edit_text(
            "Похоже, у вас уже есть активная запись на пробный урок. "
            "Вы можете проверить ее в главном меню или перенести, если это необходимо.",
            reply_markup=get_duplicate_booking_keyboard() 
        )
        await callback.answer()
        return

    await callback.message.edit_text("⏳ Минутку, бронирую для вас этот слот...")
    user_details = user_db.user_data or {}
    
    client_data = {
        'username': callback.from_user.username or "N/A",
        'parent_name': user_details.get('parent_name'),
        'child_name': user_details.get('child_name'),
        'child_age': user_details.get('child_age'),
        'child_interests': user_details.get('child_interests', 'не указаны')
    }
    
    selected_time_str = callback.data.split(":", 1)[1]
    start_time = datetime.fromisoformat(selected_time_str).replace(tzinfo=ZoneInfo("Europe/Moscow"))
    teacher_id = int(fsm_data.get("selected_teacher_id", "1"))

    logging.info(f"Вызов сервиса book_lesson для пользователя {user_db.id}. Преподаватель: {teacher_id}, Время: {start_time}")
    
    task_id, event_id, teacher_name = await book_lesson(
        user_id=teacher_id,
        start_time=start_time,
        duration_minutes=60,
        client_data=client_data
    )

    if task_id and event_id:
        await add_trial_lesson(user_db.id, task_id, event_id, teacher_id, start_time)
        lesson_time_str = format_date_russian(start_time, 'full')
        await callback.message.edit_text(
            f"✅ Отлично, все готово!\n\n"
            f"Я записал(а) вас на пробный урок для **{client_data.get('child_name')}** к преподавателю {teacher_name}.\n\n"
            f"Ждем вас {lesson_time_str}.\n\n"
            f"Напомню о занятии за день и за час до начала. До встречи!",
            reply_markup=get_final_booking_keyboard() 
        )
    else:
        await callback.message.edit_text(
            "😔 К сожалению, произошла ошибка и не удалось забронировать слот. "
            "Возможно, его только что заняли. Пожалуйста, попробуйте выбрать другое время."
        )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "initiate_reschedule")
async def handle_initiate_reschedule_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Перенести существующую".
    """
    logging.info(f"Пользователь {callback.from_user.id} нажал кнопку 'Перенести существующую'. Запускаем сценарий переноса.")
    await reschedule_handlers.start_reschedule_flow(
        message=callback.message,
        state=state,
        user_id=callback.from_user.id,
        username=callback.from_user.username
    )
    await callback.answer()


@router.callback_query(F.data == "start_booking_additional")
async def handle_start_booking_additional_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Записать еще одного ребенка".
    Просто запускает сценарий онбординга с самого начала.
    """
    logging.info(f"Пользователь {callback.from_user.id} нажал кнопку 'Записать еще одного ребенка'.")
    await callback.message.edit_text(
        "Отлично! Давайте заполним анкету для нового ученика."
    )
    # Запускаем сценарий с нуля, без всяких сложных параметров
    await onboarding_handlers.start_fsm_scenario(callback.message, state)
    await callback.answer()

# =============================================================================
# НОВЫЙ БЛОК: Обработчики для добавления второго ребенка
# =============================================================================

@router.callback_query(F.data == "add_second_child")
async def handle_add_second_child_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку "Добавить второго ребенка".
    """
    logging.info(f"User {callback.from_user.id} wants to add a second child.")
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    
    child_name_raw = user.user_data.get('child_name', 'вашего ребенка') if user.user_data else 'вашего ребенка'
    child_name = child_name_raw.capitalize()

    message_text = (
        f"Отличная идея! Если вашему второму ребенку от 10 до 17 лет, "
        f"он может просто присоединиться к пробному уроку вместе с {child_name}. "
        f"Если у вас есть вопросы или второй ребенок другого возраста, лучше уточнить у менеджера."
    )

    await callback.message.edit_text(
        message_text,
        reply_markup=get_add_second_child_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "add_second_child_confirm")
async def handle_add_second_child_confirm_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает подтверждение 'Да, отлично'.
    """
    logging.info(f"User {callback.from_user.id} confirmed the second child info.")
    
    await callback.message.edit_text(
        "Замечательно! Рады, что у вас пополнение в команде будущих программистов. "
        "Тогда ничего дополнительно делать не нужно. Ждем вас на уроке!\n\n"
        "Чем еще могу помочь?",
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Вернуться в главное меню", callback_data="main_menu").as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_second_child_manager")
async def handle_add_second_child_manager_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает запрос на вызов менеджера по вопросу второго ребенка, добавляя "человечную" паузу.
    """
    logging.info(f"Пользователь {callback.from_user.id} хочет записать ещё одного ребенка на пробное занятие")
    
    await notify_admin_of_request(
        bot=callback.bot, 
        user=callback.from_user, 
        request_text="Пользователю нужна помощь с записью второго ученика."
    )
    # Удаляем старое сообщение с кнопками
    await callback.message.delete()
    # ДЕЛАЕМ ПАУЗУ, чтобы создать ощущение выполненного действия
    await asyncio.sleep(1.5)
    
    await callback.message.answer(
        "Я передал ваш вопрос менеджеру, он скоро с вами свяжется. "
        "А пока вы можете изучить другие популярные вопросы о нашей школе.",
        # --- ИСПОЛЬЗУЕМ ИМПОРТИРОВАННУЮ ФУНКЦИЮ ---
        reply_markup=get_faq_menu()
    )
    await callback.answer()