# app/handlers/cancellation_handlers.py

import logging
from typing import Optional

from aiogram import F, Router, types
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.states.fsm_states import CancellationStates 

# --- Импорты из внутренних модулей проекта ---

# Функции для взаимодействия с базой данных
from app.db.database import (
    cancel_lesson_db,
    get_all_active_lessons,
    get_lesson_by_id,
    get_or_create_user,
    load_history)

# Сервис для работы с API Битрикс24 (отмена бронирования)
from app.services.bitrix_service import cancel_booking
# Утилита для красивого форматирования даты
from app.utils.formatters import format_date_russian
# Импорт уведомления для админа 
from app.core.admin_notifications import notify_admin_on_error


# Создаем роутер, к которому будем привязывать все обработчики этого модуля
router = Router()


class CancelCallbackFactory(CallbackData, prefix="cancel_booking"):
    """
    Фабрика колбэков для сценария отмены. Позволяет создавать и распознавать
    данные, передаваемые при нажатии на inline-кнопки.

    Атрибуты:
        action (str): Тип действия ('select', 'confirm', 'reject').
        lesson_id (Optional[int]): ID урока, с которым производится действие.
                                   Может отсутствовать, если действие не привязано
                                   к конкретному уроку (например, общая отмена).
    """
    action: str
    lesson_id: Optional[int] = None


@router.message(F.text.lower().in_(['отменить запись', 'отменить занятие']))
async def start_cancellation_flow(message: types.Message, state: FSMContext):
    """
    Запускает сценарий отмены записи.
    
    Срабатывает, когда пользователь отправляет текстовое сообщение "отменить запись" или "отменить занятие".
    1. Находит все активные (не отмененные) уроки пользователя в базе данных.
    2. Если уроков нет, сообщает об этом пользователю.
    3. Если найден один урок, сразу предлагает подтвердить его отмену.
    4. Если найдено несколько уроков, предлагает пользователю выбрать, какой именно отменить.
    """
    # Сбрасываем предыдущее состояние FSM, чтобы избежать конфликтов
    await state.clear()
    
    # Получаем или создаем пользователя в нашей БД
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    # Запрашиваем из БД список ВСЕХ активных уроков для этого пользователя
    active_lessons = await get_all_active_lessons(user.id)

    # Если список пуст, сообщаем пользователю и выходим из сценария
    if not active_lessons:
        await message.answer("Я проверил, но у вас нет запланированных пробных уроков для отмены.")
        return

    # Создаем конструктор для inline-клавиатуры
    builder = InlineKeyboardBuilder()

    # Сценарий 1: У пользователя только одна активная запись
    if len(active_lessons) == 1:
        lesson = active_lessons[0]
        lesson_time_str = format_date_russian(lesson.scheduled_at, 'short')
        
        # ИСПРАВЛЕНО: Добавлены закрывающие скобки ')' для каждого вызова .button()
        builder.button(
            text="Да, отменить запись",
            callback_data=CancelCallbackFactory(action="confirm", lesson_id=lesson.id)
        )
        builder.button(
            text="Нет, всё в силе",
            callback_data=CancelCallbackFactory(action="reject")
        )
        # Располагаем 2 кнопки в один ряд
        builder.adjust(2)

        await message.answer(
            f"У вас запланирован урок на {lesson_time_str}.\n\n"
            f"Вы уверены, что хотите отменить эту запись?",
            reply_markup=builder.as_markup()
        )

    # Сценарий 2: У пользователя несколько активных записей
    else:
        await message.answer("У вас есть несколько активных записей. Какую из них вы хотите отменить?")
        
        # Создаем кнопку для каждого урока
        for lesson in active_lessons:
            child_name = lesson.user.user_data.get('child_name', 'ребенка') if lesson.user.user_data else 'ребенка'
            lesson_time_str = format_date_russian(lesson.scheduled_at, 'short')
            child_name = "ребенка" # Временно упрощаем для надежности
            lesson_time_str = format_date_russian(lesson.scheduled_at, 'short')
            builder.button(
                text=f"Урок для {child_name} на {lesson_time_str}",
                callback_data=CancelCallbackFactory(action="select", lesson_id=lesson.id)
            )
        
        # Добавляем общую кнопку для выхода из сценария
        builder.button(text="Я передумал(а)", callback_data=CancelCallbackFactory(action="reject"))
        # Располагаем каждую кнопку на новой строке для лучшей читаемости
        builder.adjust(1)
        
        await message.answer("Выберите урок:", reply_markup=builder.as_markup())


@router.callback_query(CancelCallbackFactory.filter(F.action == "select"))
async def select_lesson_to_cancel(callback: types.CallbackQuery, callback_data: CancelCallbackFactory):
    """
    Обрабатывает выбор конкретного урока из списка (когда у пользователя несколько записей).
    
    Срабатывает, когда пользователь нажимает на кнопку с `action="select"`.
    1. Получает из БД информацию о выбранном уроке по его `lesson_id`.
    2. Показывает детали урока и запрашивает финальное подтверждение отмены.
    """
    lesson = await get_lesson_by_id(callback_data.lesson_id)
    if not lesson:
        await callback.message.edit_text("Не удалось найти этот урок. Возможно, он уже был отменен.")
        await callback.answer()
        return

    lesson_time_str = format_date_russian(lesson.scheduled_at, 'short')
    builder = InlineKeyboardBuilder()

    # ИСПРАВЛЕНО: Добавлены закрывающие скобки ')' для каждого вызова .button()
    builder.button(
        text="Да, точно отменить",
        callback_data=CancelCallbackFactory(action="confirm", lesson_id=lesson.id)
    )
    builder.button(
        text="Нет, вернуться",
        callback_data=CancelCallbackFactory(action="reject")
    )
    builder.adjust(2)

    await callback.message.edit_text(
        f"Вы выбрали урок на {lesson_time_str}. Подтверждаете отмену?",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(CancelCallbackFactory.filter(F.action == "confirm"))
async def confirm_cancellation_and_ask_reason(callback: types.CallbackQuery, callback_data: CancelCallbackFactory, state: FSMContext):
    """
    Шаг 1: Пользователь подтвердил отмену. Теперь запрашиваем причину.
    """
    await state.update_data(lesson_id_to_cancel=callback_data.lesson_id)
    await state.set_state(CancellationStates.awaiting_reason)
    
    await callback.message.edit_text(
        "Понял вас. Чтобы мы могли стать лучше, напишите, пожалуйста, в двух словах, почему вы решили отменить запись?"
    )
    await callback.answer()

# --- НОВЫЙ ХЕНДЛЕР ДЛЯ ОБРАБОТКИ ПРИЧИНЫ ---
@router.message(CancellationStates.awaiting_reason, F.text)
async def process_cancellation_reason(message: types.Message, state: FSMContext):
    """
    Шаг 2: Пользователь прислал причину. Выполняем отмену и завершаем процесс.
    """
    cancellation_reason = message.text
    user_data = await state.get_data()
    lesson_id = user_data.get('lesson_id_to_cancel')
    
    await state.clear()
    
    await message.answer("Спасибо за обратную связь! Минутку, обрабатываю отмену...")

    active_lesson = await get_lesson_by_id(lesson_id)

    # Сначала проверяем, что урок найден, и только потом — его детали.
    if not active_lesson:
        await message.answer("Произошла ошибка: не могу найти данные о вашей записи. Возможно, она уже отменена.")
        return
    # Теперь, когда мы уверены, что active_lesson существует, проверяем его поля.
    if not all([active_lesson.task_id, active_lesson.event_id, active_lesson.teacher_id]):
        error_description = f"Данные для отмены урока ID {active_lesson.id} в локальной БД неполные! Невозможно выполнить отмену в Bitrix24. Требуется ручная проверка."
        logging.error(f"Критическая ошибка для пользователя {message.from_user.id}: {error_description}")
        
        # Вызываем администратора, чтобы он вручную проверил и удалил запись
        history = await load_history(str(message.from_user.id))
        await notify_admin_on_error(
            bot=message.bot,
            user_id=message.from_user.id,
            username=message.from_user.username,
            error_description=error_description,
            history=history
        )
        
        await message.answer("Произошла внутренняя ошибка: данные о вашей записи в CRM неполные. Я уже сообщил администратору, он свяжется с вами для решения проблемы.")
        return

    # Вызываем наш новый, улучшенный сервис
    success = await cancel_booking(
        task_id=active_lesson.task_id,
        event_id=active_lesson.event_id,
        owner_id=active_lesson.teacher_id,
        reason=cancellation_reason  # <-- Передаем причину!
    )

    if success:
        await cancel_lesson_db(active_lesson.id)
        await message.answer(
            "Готово! Ваша запись на урок отменена. Мы учтем ваш отзыв. "
            "Если захотите записаться снова — я к вашим услугам!"
        )
    else:
        error_description = f"Не удалось отменить бронирование в Bitrix24. Задача: {active_lesson.task_id}, Событие: {active_lesson.event_id}"
        logging.error(f"Ошибка для пользователя {message.from_user.id}: {error_description}")
        
        # Вызываем администратора, чтобы он вручную проверил и удалил запись
        history = await load_history(str(message.from_user.id))
        await notify_admin_on_error(
            bot=message.bot,
            user_id=message.from_user.id,
            username=message.from_user.username,
            error_description=error_description,
            history=history
        )
        
        await message.answer(
            "К сожалению, при отмене произошла техническая ошибка в CRM. "
            "Я уже сообщил об этом администратору, он разберется в ситуации."
        )


@router.callback_query(CancelCallbackFactory.filter(F.action == "reject"))
async def reject_cancellation(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает отказ от отмены на любом из этапов.

    Срабатывает, когда пользователь нажимает кнопку с `action="reject"`.
    Просто сообщает, что запись остается в силе, и завершает диалог.
    """
    await callback.message.edit_text("Отлично! Ваша запись остается в силе. С нетерпением ждем вас на уроке!")
    await callback.answer()

