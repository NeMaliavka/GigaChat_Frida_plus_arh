# app/handlers/onboarding_handlers.py

import json
import logging
from html import escape
from pathlib import Path
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.states.fsm_states import GenericFSM
from app.utils.formatters import format_response_with_inflection
from app.core.business_logic import process_final_data
from app.core.admin_notifications import notify_admin_on_error
from app.db.database import save_user_details, set_onboarding_completed, load_history
from app.handlers import booking_handlers

# --- 1. ИНИЦИАЛИЗАЦИЯ И ЗАГРУЗКА СЦЕНАРИЯ ---
router = Router()
FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"

try:
    with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
        FSM_CONFIG = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить FSM-сценарий. {e}")
    FSM_CONFIG = {}

# Опциональный импорт для расширенных функций
try:
    from app.utils.text_tools import correct_keyboard_layout, is_plausible_name
    MORPHOLOGY_ENABLED = True
except ImportError:
    logging.warning("Утилиты (text_tools.py) не найдены. Расширенные функции будут отключены.")
    MORPHOLOGY_ENABLED = False
    def correct_keyboard_layout(_: str) -> None: return None
    def is_plausible_name(_: str) -> bool: return True


# --- 2. ФУНКЦИЯ ДЛЯ СОЗДАНИЯ КНОПОК ИЗ СЦЕНАРИЯ ---
def create_fsm_keyboard(keyboard_data: list | None) -> types.InlineKeyboardMarkup | None:
    """Создает инлайн-клавиатуру из данных, полученных из fsm_scenario.json."""
    if not keyboard_data:
        return None
    builder = InlineKeyboardBuilder()
    for row in keyboard_data:
        buttons = [types.InlineKeyboardButton(text=button_data['text'], callback_data=button_data['callback_data']) for button_data in row]
        builder.row(*buttons)
    return builder.as_markup()


# --- 3. ФУНКЦИЯ, КОТОРАЯ ОТПРАВЛЯЕТ ВОПРОС С КНОПКАМИ ---
async def _ask_next_question(message: types.Message, state: FSMContext, step_name: str):
    """Вспомогательная функция, которая задает вопрос и прикрепляет кнопки."""
    step_config = FSM_CONFIG.get("states", {}).get(step_name)
    if not step_config:
        logging.error(f"Ошибка конфигурации: не найден шаг '{step_name}'.")
        await message.answer("Ой, у меня техническая заминка. Пожалуйста, попробуйте позже.")
        await state.clear()
        return

    await state.update_data(current_step=step_name)
    fsm_data = await state.get_data()
    
    question_text = format_response_with_inflection(step_config.get("question"), fsm_data.get("user_answers", {}))
    keyboard = create_fsm_keyboard(step_config.get("keyboard"))
        
    await message.answer(question_text, reply_markup=keyboard)


# --- 4. ФУНКЦИЯ ДЛЯ ЗАВЕРШЕНИЯ ОНБОРДИНГА ---
async def _finish_fsm(message: types.Message, state: FSMContext):
    """Завершает FSM, обрабатывает данные, сохраняет их и предлагает записаться на урок."""
    fsm_data = await state.get_data()
    user_answers = fsm_data.get("user_answers", {})

    await save_user_details(telegram_id=message.from_user.id, data=user_answers)
    await set_onboarding_completed(message.from_user.id)
    logging.info(f"Онбординг для пользователя {message.from_user.id} завершен и данные сохранены.")
    
    processed_data = process_final_data(user_answers)
    final_template = FSM_CONFIG.get("final_message_template", "Спасибо! Теперь я знаю все необходимое.")
    final_text = format_response_with_inflection(final_template, processed_data)

    booking_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выбрать время урока", callback_data="start_booking")]
    ])
    await message.answer(final_text, reply_markup=booking_keyboard)
    await state.clear()


# --- 5. ЕДИНАЯ И ГИБКАЯ ФУНКЦИЯ ДЛЯ ЗАПУСКА СЦЕНАРИЯ ---
async def start_fsm_scenario(message: types.Message, state: FSMContext, start_node: str | None = None, intro_text: str | None = None):
    """
    Запускает FSM-сценарий. Может начинать с начала или с указанного шага,
    а также принимать специальный текст для приветствия.
    """
    if not FSM_CONFIG:
        await message.answer("Извините, функция записи временно недоступна.")
        return

    initial_step_name = start_node or FSM_CONFIG.get("initial_state")
    initial_step_config = FSM_CONFIG.get("states", {}).get(initial_step_name)
    if not initial_step_config:
        logging.error(f"Критическая ошибка: не найден шаг '{initial_step_name}' в fsm_scenario.json")
        await message.answer("Ой, у меня небольшая техническая заминка.")
        return

    logging.info(f"Запускаем сценарий для {message.from_user.id}, начиная с шага '{initial_step_name}'.")
    await state.set_state(GenericFSM.InProgress)
    
    if intro_text:
        await message.answer(intro_text)
    
    await _ask_next_question(message, state, initial_step_name)


# --- 6. ОБРАБОТЧИК КНОПОК НАВИГАЦИИ ВНУТРИ FSM ---
@router.callback_query(F.data.startswith("fsm_"))
async def handle_fsm_navigation(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает навигационные кнопки 'назад' и 'отмена'."""
    action = callback.data.split(":")[0]
    
    if action == "fsm_cancel":
        logging.info(f"Пользователь {callback.from_user.id} отменил FSM-сценарий.")
        await state.clear()
        await callback.message.edit_text("Хорошо, запись отменена. Если передумаете, я всегда здесь!")
        
    elif action == "fsm_back":
        target_step = callback.data.split(":")[1]
        logging.info(f"Пользователь {callback.from_user.id} вернулся на шаг '{target_step}'.")
        await callback.message.delete()
        await _ask_next_question(callback.message, state, target_step)
        
    await callback.answer()

# --- 7. ЕДИНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ ТЕКСТОВЫХ ОТВЕТОВ ВНУТРИ FSM ---
@router.message(GenericFSM.InProgress)
async def handle_fsm_step(message: types.Message, state: FSMContext):
    """Обрабатывает ответ пользователя на любом шаге сценария."""
    user_text = message.text.strip()
    fsm_data = await state.get_data()
    current_step_name = fsm_data.get("current_step")
    
    if not current_step_name:
        logging.warning(f"Получен ответ от {message.from_user.id}, но текущий шаг FSM не определен.")
        return

    current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name)
    if not current_step_config:
        error_text = f"Ошибка в конфигурации сценария. Не найден шаг: {current_step_name}"
        history = await load_history(str(message.from_user.id), limit=10)
        await notify_admin_on_error(bot=message.bot, user_id=message.from_user.id, username=message.from_user.username, error_description=error_text, history=history)
        await message.answer("Ой, у меня техническая заминка. Уже позвал администратора, он скоро подключится!")
        await state.clear()
        return

    # Валидация ввода
    validation_type = current_step_config.get("validation")
    is_valid = True
    if validation_type:
        if validation_type == "name" and MORPHOLOGY_ENABLED:
            is_valid = is_plausible_name(user_text)
        elif validation_type == "digits":
            is_valid = user_text.isdigit()
        
        if not is_valid:
            await message.answer(current_step_config.get("error_message", "Неверный формат. Пожалуйста, попробуйте еще раз."))
            return

    # Сохранение данных
    data_key = current_step_config["data_key"]
    value_to_store = int(user_text) if validation_type == "digits" else user_text
    current_answers = fsm_data.get("user_answers", {})
    current_answers[data_key] = value_to_store
    await state.update_data(user_answers=current_answers)
    
    # --- ЛОГИКА ОБРАБОТКИ ВОЗРАСТА ---
    if data_key == 'child_age':
        age = value_to_store
        if age < 9:
            response_text = "На данный момент наши курсы рассчитаны на детей от 9 лет, но мы уже активно создаем программу для самых юных программистов!\n\nХотите, мы сообщим вам о запуске в числе первых? Это бесплатно и ни к чему не обязывает."
            buttons = [
                InlineKeyboardButton(text="Да, сообщите мне!", callback_data="waitlist:join"),
                InlineKeyboardButton(text="Нет, спасибо", callback_data="waitlist:cancel")
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            await message.answer(response_text, reply_markup=reply_markup)
            await set_onboarding_completed(message.from_user.id) # Считаем онбординг завершенным
            await save_user_details(telegram_id=message.from_user.id, data=current_answers)
            await state.clear()
            return
        elif age > 17:
            response_text = "Здорово! В таком возрасте мы бы уже рекомендовали взрослые курсы для достижения максимального результата. У нас таких, к сожалению, нет, но мы уверены, что вы найдете отличный вариант!"
            await message.answer(response_text)
            await set_onboarding_completed(message.from_user.id) # Считаем онбординг завершенным
            await save_user_details(telegram_id=message.from_user.id, data=current_answers)
            await state.clear()
            return

    next_step_name = current_step_config.get("next_state")
    if next_step_name:
        await _ask_next_question(message, state, next_step_name)
    else:
        # Если следующего шага нет, значит, мы на последнем шаге (confirm_data).
        # Ничего не делаем, просто ждем нажатия на одну из кнопок:
        # "Все верно", "Исправить" или "Отменить".
        logging.info(f"Достигнут финальный шаг '{current_step_name}'. Ожидание нажатия кнопки подтверждения.")
        pass
