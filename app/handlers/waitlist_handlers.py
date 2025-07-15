# app/handlers/waitlist_handlers.py
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from app.db.database import get_or_create_user, save_user_details
from app.states.fsm_states import WaitlistFSM

router = Router()

@router.callback_query(F.data == "waitlist:join")
async def handle_waitlist_join(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отлично! Пожалуйста, оставьте ваш номер телефона или email, и мы сообщим о запуске.")
    await state.set_state(WaitlistFSM.waiting_for_contact)
    await callback.answer()

@router.callback_query(F.data == "waitlist:cancel")
async def handle_waitlist_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Хорошо, мы вас поняли. Если передумаете, мы всегда на связи!")
    await callback.answer()

@router.message(WaitlistFSM.waiting_for_contact)
async def process_waitlist_contact(message: types.Message, state: FSMContext):
    contact_info = message.text
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    
    current_data = user.user_data or {}
    current_data['waitlist_contact'] = contact_info
    current_data['waitlist_for_age'] = '<9' # или другой идентификатор
    
    await save_user_details(telegram_id=user.telegram_id, data=current_data)
    logging.info(f"Пользователь {user.telegram_id} добавлен в лист ожидания: {contact_info}")
    
    await message.answer("Спасибо! Мы сохранили ваши данные и обязательно с вами свяжемся.")
    await state.clear()
