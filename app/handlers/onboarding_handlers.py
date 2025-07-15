# app/handlers/onboarding_handlers.py
import json
import logging
from pathlib import Path
from html import escape

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.states.fsm_states import GenericFSM
from app.utils.formatters import format_response_with_inflection
from app.core.business_logic import process_final_data
from app.core.admin_notifications import notify_admin_on_error
from app.db.database import save_user_details, set_onboarding_completed, load_history

# --- ИНИЦИАЛИЗАЦИЯ И ЗАГРУЗКА СЦЕНАРИЯ ---
router = Router()
FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"

try:
    with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
        FSM_CONFIG = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"Критическая ошибка: не удалось загрузить FSM-сценарий. {e}")
    FSM_CONFIG = {}

# Импортируем утилиты для валидации и коррекции
try:
    from app.utils.text_tools import correct_keyboard_layout, is_plausible_name
    MORPHOLOGY_ENABLED = True
except ImportError:
    logging.warning("Утилиты (text_tools.py) не найдены. Расширенные функции будут отключены.")
    MORPHOLOGY_ENABLED = False
    def correct_keyboard_layout(_: str) -> None: return None
    def is_plausible_name(_: str) -> bool: return True

# --- ЛОГИКА FSM-СЦЕНАРИЯ (ОНБОРДИНГ) ---

async def start_fsm_scenario(message: types.Message, state: FSMContext):
    """Запускает FSM-сценарий, задавая самый первый вопрос."""
    if not FSM_CONFIG:
        await message.answer("Извините, функция записи временно недоступна.")
        return

    initial_step_name = FSM_CONFIG.get("initial_state")
    initial_step_config = FSM_CONFIG.get("states", {}).get(initial_step_name)

    if not initial_step_config:
        logging.error("Критическая ошибка: не найден initial_state в fsm_scenario.json")
        await message.answer("Ой, у меня небольшая техническая заминка.")
        return

    logging.info(f"Запускаем сценарий '{FSM_CONFIG.get('scenario_name', 'N/A')}' для {message.from_user.id}")
    await state.set_state(GenericFSM.InProgress)
    await state.set_data({'current_step': initial_step_name})
    
    intro_text = FSM_CONFIG.get("onboarding_intro", "")
    first_question = initial_step_config.get("question", "Как я могу к вам обращаться?")
    
    await message.answer(intro_text + first_question)


async def _advance_fsm_step(message: types.Message, state: FSMContext, fsm_data: dict):
    """Продвигает пользователя на следующий шаг или завершает сценарий."""
    current_step_name = fsm_data.get("current_step")
    current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name, {})
    next_step_name = current_step_config.get("next_state")

    if next_step_name:
        next_step_config = FSM_CONFIG.get("states", {}).get(next_step_name)
        if not next_step_config: 
            logging.error(f"Ошибка конфигурации: не найден следующий шаг '{next_step_name}'")
            await message.answer("Ой, у меня техническая заминка. Пожалуйста, попробуйте позже.")
            await state.clear()
            return

        fsm_data['current_step'] = next_step_name
        await state.set_data(fsm_data)
        
        next_question = format_response_with_inflection(next_step_config.get("question"), fsm_data)
        await message.answer(next_question)
    else:
        # Финал сценария
        await set_onboarding_completed(message.from_user.id)
        processed_data = process_final_data(fsm_data)
        
        final_template = FSM_CONFIG.get("final_message_template", "Спасибо!")
        final_text = format_response_with_inflection(final_template, processed_data)
        
        booking_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выбрать время урока", callback_data="start_booking")]
        ])
        
        await message.answer(final_text, reply_markup=booking_keyboard)
        await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
        await state.clear()


@router.callback_query(F.data.startswith("confirm_layout:"))
async def process_layout_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение коррекции раскладки."""
    fsm_data = await state.get_data()
    action = callback.data.split(":")[1]
    
    final_input = fsm_data.get("suggested_input") if action == "yes" else fsm_data.get("original_input")
    
    await callback.message.edit_text(f"Отлично! Записал: {final_input.capitalize()}.")
    
    target_key = fsm_data.pop("target_data_key")
    fsm_data[target_key] = final_input
    
    # Очищаем временные данные
    fsm_data.pop("original_input", None)
    fsm_data.pop("suggested_input", None)
    await state.set_data(fsm_data)
    
    # Продвигаем сценарий дальше
    await _advance_fsm_step(callback.message, state, fsm_data)
    await callback.answer()


@router.message(GenericFSM.InProgress)
async def handle_fsm_step(message: types.Message, state: FSMContext):
    """Обрабатывает ответ пользователя на любом шаге основного сценария."""
    user_text = message.text.strip()
    fsm_data = await state.get_data()
    current_step_name = fsm_data.get("current_step")
    current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name)

    if not current_step_config:
        error_text = f"Ошибка в конфигурации сценария. Не найден шаг: {current_step_name}"
        history = await load_history(str(message.from_user.id), limit=10)
        await notify_admin_on_error(bot=message.bot, user_id=message.from_user.id, username=message.from_user.username, error_description=error_text, history=history)
        await message.answer("Ой, у меня техническая заминка. Уже позвал администратора, он скоро подключится!")
        await state.clear()
        return

    # Проверка на коррекцию раскладки клавиатуры
    if MORPHOLOGY_ENABLED and current_step_config.get("needs_layout_correction", False):
        if corrected_text := correct_keyboard_layout(user_text):
            await state.update_data(original_input=user_text, suggested_input=corrected_text, target_data_key=current_step_config["data_key"])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"Да, это «{corrected_text.capitalize()}»", callback_data="confirm_layout:yes")],
                [InlineKeyboardButton(text="Нет, оставить как есть", callback_data="confirm_layout:no")]
            ])
            await message.answer(f"Вы ввели «{escape(user_text)}». Возможно, вы имели в виду «{corrected_text.capitalize()}»?", reply_markup=keyboard)
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
        await message.answer(current_step_config.get("error_message", "Неверный формат."))
        return

    # Сохранение данных и проверка особых условий
    data_key = current_step_config["data_key"]
    value_to_store = int(user_text) if validation_type == "digits" else user_text
    fsm_data[data_key] = value_to_store
    
    # Особая логика для возраста ребенка
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
            
            await set_onboarding_completed(message.from_user.id) # Считаем онбординг пройденным
            await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
            await state.clear()
            return
        elif age > 17:
            response_text = "Здорово! В таком возрасте мы бы уже рекомендовали взрослые курсы для достижения максимального результата. У нас таких, к сожалению, нет, но мы уверены, что вы найдете отличный вариант!"
            await message.answer(response_text)

            await set_onboarding_completed(message.from_user.id)
            await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
            await state.clear()
            return

    # Переход к следующему шагу
    await _advance_fsm_step(message, state, fsm_data)
