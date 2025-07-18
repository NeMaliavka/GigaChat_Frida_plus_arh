# app/handlers/reschedule_handlers.py

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Меняем импорт get_active_lesson на get_all_active_lessons и добавляем get_lesson_by_id
from app.db.database import (
    get_or_create_user,
    get_all_active_lessons,
    get_lesson_by_id,
    update_trial_lesson_time
)
from app.states.fsm_states import BookingFSM
from app.handlers.utils.booking_utils import show_available_dates, get_time_keyboard
from app.services.bitrix_service import reschedule_booking
from app.utils.formatters import format_date_russian

router = Router()

# Эта функция больше не нужна, так как интент будет обрабатываться напрямую в sales_funnel.
# Мы оставляем ее закомментированной для истории.
# async def initiate_reschedule_from_text(message: types.Message, state: FSMContext):
#     """Инициирует сценарий переноса из текстового сообщения."""
#     logging.info(f"Запрос на перенос от {message.from_user.id} через текст. Предлагаем кнопку.")
#     keyboard = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Перенести запись", callback_data="initiate_reschedule")]
#     ])
#     await message.answer(
#         "Вы хотите перенести существующую запись на другое время?",
#         reply_markup=keyboard
#     )


async def start_reschedule_flow(message: types.Message, state: FSMContext, user_id: int | None = None, username: str | None = None):
    """
    Находит все активные уроки пользователя.
    Если урок один - запрашивает подтверждение переноса.
    Если уроков несколько - предлагает выбрать, какой перенести.
    """
    await state.clear()
    # Если ID пользователя не передан явно, берем его из сообщения
    if user_id is None:
        user_id = message.from_user.id
        username = message.from_user.username
    logging.info(f"Запуск сценария переноса для пользователя {user_id}.")
    user = await get_or_create_user(user_id, username)
    
    # Получаем ВСЕ активные уроки
    active_lessons = await get_all_active_lessons(user.id)

    if not active_lessons:
        logging.warning(f"Пользователь {user.id} попытался перенести запись, но активных уроков нет.")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Да, записаться", callback_data="start_booking")]])
        await message.answer(
            "Я проверил, но у вас нет запланированных уроков для переноса.\n\n"
            "Давайте я помогу вам записаться на новый?",
            reply_markup=keyboard
        )
        return

    if len(active_lessons) == 1:
        # Если урок только один, сразу переходим к подтверждению
        lesson = active_lessons[0]
        await _prompt_reschedule_confirmation(message, state, lesson)
    else:
        # Если уроков несколько, строим клавиатуру для выбора
        logging.info(f"У пользователя {user.id} найдено несколько ({len(active_lessons)}) активных уроков. Предлагаем выбор.")
        builder = InlineKeyboardBuilder()
        for lesson in active_lessons:
            lesson_time_str = format_date_russian(lesson.scheduled_at, 'short')
            child_name = lesson.user.user_data.get('child_name', 'ребенка') if lesson.user.user_data else 'ребенка'
            builder.button(
                text=f"Урок для {child_name} на {lesson_time_str}",
                callback_data=f"select_reschedule:{lesson.id}"
            )
        builder.adjust(1)
        await message.answer("У вас есть несколько активных записей. Какую из них вы хотите перенести?", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("select_reschedule:"))
async def handle_lesson_selection_for_reschedule(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор конкретного урока из списка для переноса.
    """
    lesson_id = int(callback.data.split(":")[1])
    logging.info(f"Пользователь {callback.from_user.id} выбрал для переноса урок с ID {lesson_id}.")
    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        logging.error(f"Не удалось найти урок с ID {lesson_id} после выбора пользователем.")
        await callback.message.edit_text("Не удалось найти этот урок. Возможно, он уже был отменен.")
        await callback.answer()
        return

    # Вызываем ту же функцию подтверждения, что и для одного урока
    await _prompt_reschedule_confirmation(callback.message, state, lesson, is_callback=True)
    await callback.answer()


async def _prompt_reschedule_confirmation(message: types.Message, state: FSMContext, lesson, is_callback: bool = False):
    """
    Вспомогательная функция. Запрашивает у пользователя подтверждение переноса для конкретного урока.
    """
    # Убеждаемся, что scheduled_at - это действительно объект datetime
    if not isinstance(lesson.scheduled_at, datetime):
        logging.error(f"Критическая ошибка: у активного урока {lesson.id} отсутствует дата. Перенос невозможен.")
        await message.answer("Произошла внутренняя ошибка. Не удалось определить дату вашего урока. Пожалуйста, свяжитесь с поддержкой.")
        return

    # Сохраняем все необходимые данные для последующих шагов
    await state.update_data(
        lesson_to_reschedule_id=lesson.id,
        task_id=lesson.task_id,
        event_id=lesson.event_id,
        teacher_id=lesson.teacher_id,
        old_start_time=lesson.scheduled_at.isoformat()
    )

    lesson_time_str = format_date_russian(lesson.scheduled_at, 'full')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, выбрать новое время", callback_data="confirm_reschedule")],
        [InlineKeyboardButton(text="Нет, я передумал(а)", callback_data="cancel_action")]
    ])
    
    text = f"Ваш урок запланирован на **{lesson_time_str}**.\n\nВы хотите перенести его на другое время?"
    
    if is_callback:
        # Если это callback (после выбора из списка), редактируем сообщение
        await message.edit_text(text, reply_markup=keyboard)
    else:
        # Если это обычное сообщение (когда урок один), отправляем новое
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "confirm_reschedule")
async def confirm_reschedule(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждает перенос и запускает показ свободных дат."""
    await callback.message.edit_text("Отлично! Давайте подберем новое время.")
    await state.set_state(BookingFSM.rescheduling_in_progress)
    await show_available_dates(callback, state) # Используем общую утилиту для показа дат
    await callback.answer()


@router.callback_query(BookingFSM.rescheduling_in_progress, F.data.startswith("book_date:"))
async def handle_reschedule_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор ДАТЫ в сценарии переноса, СОХРАНЯЯ ПРАВИЛЬНОЕ СОСТОЯНИЕ."""
    selected_date = callback.data.split(":")[1]
    logging.info(f"В сценарии переноса пользователь {callback.from_user.id} выбрал дату: {selected_date}")
    await state.update_data(selected_date=selected_date)
    keyboard = await get_time_keyboard(state, selected_date)
    await callback.message.edit_text(f"Вы выбрали {selected_date}. Теперь выберите удобное время:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BookingFSM.rescheduling_in_progress, F.data.startswith("book_time:"))
async def handle_reschedule_time_selection(callback: types.CallbackQuery, state: FSMContext):
    """Ловит финальный выбор ВРЕМЕНИ, вызывает сервис ПЕРЕНОСА и завершает процесс."""
    await callback.message.edit_text("Минутку, переношу вашу запись на новое время...")
    fsm_data = await state.get_data()
    
    lesson_id = fsm_data.get("lesson_to_reschedule_id")
    # Теперь эта функция вернет нам урок вместе с данными пользователя
    lesson = await get_lesson_by_id(lesson_id)
    if not lesson or not lesson.user:
        await callback.message.edit_text("Не удалось найти исходную запись или ее пользователя. Попробуйте снова.")
        await state.clear()
        return

    # --- ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ: Берем данные из анкеты СВЯЗАННОГО пользователя ---
    client_data = lesson.user.user_data or {}
    client_data['username'] = callback.from_user.username # Добавляем актуальный username
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    datetime_str = callback.data.split(":", 1)[1]
    new_start_time = datetime.fromisoformat(datetime_str).replace(tzinfo=ZoneInfo("Europe/Moscow"))
    old_start_time = lesson.scheduled_at

    logging.info(f"Вызов сервиса reschedule_booking для урока {lesson_id}. Новое время: {new_start_time}")
    
    success = await reschedule_booking(
        task_id=lesson.task_id,
        event_id=lesson.event_id,
        old_start_time=old_start_time,
        new_start_time=new_start_time,
        teacher_id=lesson.teacher_id,
        client_data=client_data  # Передаем правильные данные из профиля
    )

    if success:
        await update_trial_lesson_time(lesson_id, new_start_time)
        new_time_str = format_date_russian(new_start_time, 'short')
        await callback.message.edit_text(f"✅ Готово! Ваша запись успешно перенесена на {new_time_str}.")
    else:
        await callback.message.edit_text("😔 К сожалению, не удалось перенести запись. Слот мог быть занят. Попробуйте снова или свяжитесь с менеджером.")
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_action")
async def cancel_any_action(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет любой текущий процесс."""
    logging.info(f"Пользователь {callback.from_user.id} отменил текущее действие.")
    await state.clear()
    await callback.message.edit_text("Хорошо, я отменил операцию. Если что-то понадобится — обращайтесь!")
    await callback.answer()
