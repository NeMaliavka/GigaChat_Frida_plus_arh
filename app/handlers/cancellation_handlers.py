# app/handlers/cancellation_handlers.py

import logging
from aiogram import Router, types, F
from aiogram.filters.callback_data import CallbackData # <-- ИЗМЕНЕНИЕ 1: Правильный импорт
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.database import get_or_create_user, get_active_lesson, cancel_lesson_db 
from app.services.bitrix_service import cancel_booking

router = Router()

# ИЗМЕНЕНИЕ 2: Создаем фабрику CallbackData вместо наследования от CallbackQuery
class CancelCallbackFactory(CallbackData, prefix="cancel_booking"):
    action: str # "confirm" или "reject"

async def start_cancellation_flow(message: types.Message, state: FSMContext):
    """Начинает процесс отмены: проверяет наличие записи и запрашивает подтверждение."""
    await state.clear()
    
    # В user_id теперь нужно брать ID из нашей БД, а не telegram_id
    # Предполагаем, что у вас есть функция для получения пользователя
    # from app.db.database import get_or_create_user
    # user_db = await get_or_create_user(message.from_user)
    # active_lesson = await get_active_lesson(user_db.id)
    
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    active_lesson = await get_active_lesson(user.id) # Используем user.id, а не telegram_id

    if not active_lesson:
        await message.answer("Я проверил, но у вас нет запланированных пробных уроков для отмены. Возможно, я могу помочь чем-то еще?")
        return

    lesson_time_str = active_lesson.scheduled_at.strftime("%d.%m.%Y в %H:%M")

    builder = InlineKeyboardBuilder()
    # ИЗМЕНЕНИЕ 3: Используем новую фабрику для создания данных
    builder.button(text="Да, отменить запись", 
                   callback_data=CancelCallbackFactory(action="confirm").pack())
    builder.button(text="Нет, всё в силе", 
                   callback_data=CancelCallbackFactory(action="reject").pack())
    
    await message.answer(
        f"У вас запланирован урок на {lesson_time_str}.\n\nВы уверены, что хотите отменить эту запись?",
        reply_markup=builder.as_markup()
    )

# Фильтруем по новой фабрике
@router.callback_query(CancelCallbackFactory.filter(F.action == "confirm"))
async def confirm_cancellation(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение отмены.
    Обрабатывает подтверждение отмены: удаляет из Битрикс24 и меняет статус в БД."""
    await callback.message.edit_text("Минутку, отменяю вашу запись...")

    # Повторно получаем ID пользователя и активный урок для надежности
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    active_lesson = await get_active_lesson(user.id)

    if not active_lesson or not active_lesson.task_id or not active_lesson.event_id:
        await callback.message.edit_text("Произошла ошибка: не могу найти данные о вашей записи. Пожалуйста, свяжитесь с администратором.")
        await callback.answer()
        return

    success = await cancel_booking(
        task_id=active_lesson.task_id,
        event_id=active_lesson.event_id
    )

    if success:
        await cancel_lesson_db(active_lesson.id)
        await callback.message.edit_text("Готово! Ваша запись на пробный урок успешно отменена. Если захотите записаться снова — просто напишите мне.")
    else:
        await callback.message.edit_text("К сожалению, при отмене произошла ошибка на стороне сервера. Мы уже разбираемся. Пожалуйста, попробуйте отменить запись позднее или свяжитесь с администратором.")
    
    await callback.answer()

@router.callback_query(CancelCallbackFactory.filter(F.action == "reject"))
async def reject_cancellation(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает отказ от отмены."""
    await callback.message.edit_text("Отлично! Ваша запись остается в силе. С нетерпением ждем вас на уроке!")
    await callback.answer()

