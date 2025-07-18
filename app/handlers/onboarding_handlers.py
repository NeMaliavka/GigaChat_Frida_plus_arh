# # app/handlers/onboarding_handlers.py
# import json
# import logging
# from pathlib import Path
# from html import escape

# from aiogram import Router, types, F
# from aiogram.fsm.context import FSMContext
# from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# from app.states.fsm_states import GenericFSM
# from app.utils.formatters import format_response_with_inflection
# from app.core.business_logic import process_final_data
# from app.core.admin_notifications import notify_admin_on_error
# from app.db.database import save_user_details, set_onboarding_completed, load_history
# # Импортируем обработчик для "бесшовного" перехода
# from app.handlers import booking_handlers

# # --- ИНИЦИАЛИЗАЦИЯ И ЗАГРУЗКА СЦЕНАРИЯ ---
# router = Router()
# FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"

# try:
#     with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
#         FSM_CONFIG = json.load(f)
# except (FileNotFoundError, json.JSONDecodeError) as e:
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
from app.handlers import booking_handlers

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

async def start_fsm_scenario(message: types.Message, state: FSMContext, start_node: str | None = None, intro_text: str | None = None):
    """
    Запускает FSM-сценарий. Может начинать с начала или с указанного шага,
    а также принимать специальный текст для приветствия.
    """
    if not FSM_CONFIG:
        await message.answer("Извините, функция записи временно недоступна.")
        return

    # Определяем, с какого шага начинать: с переданного или с начального по умолчанию
    initial_step_name = start_node or FSM_CONFIG.get("initial_state")
    initial_step_config = FSM_CONFIG.get("states", {}).get(initial_step_name)

    if not initial_step_config:
        logging.error(f"Критическая ошибка: не найден шаг '{initial_step_name}' в fsm_scenario.json")
        await message.answer("Ой, у меня небольшая техническая заминка.")
        return

    logging.info(f"Запускаем сценарий '{FSM_CONFIG.get('scenario_name', 'N/A')}' для {message.from_user.id}, начиная с шага '{initial_step_name}'.")

    # Устанавливаем состояние FSM
    await state.set_state(GenericFSM.InProgress)

    # --- Новая логика отправки приветствия ---
    # Если нам передали специальный текст (например, для второго ребенка), показываем его.
    if intro_text:
        await message.answer(intro_text)
    elif start_node is None and "onboarding_intro" in FSM_CONFIG:
        await message.answer(FSM_CONFIG["onboarding_intro"])

    await _ask_next_question(message, state, initial_step_name)

async def _ask_next_question(message: types.Message, state: FSMContext, step_name: str):
    """
    Вспомогательная функция, которая задает вопрос для указанного шага FSM.
    """
    step_config = FSM_CONFIG.get("states", {}).get(step_name)
    if not step_config:
        logging.error(f"Ошибка конфигурации: не найден шаг '{step_name}' для вопроса.")
        await message.answer("Ой, у меня техническая заминка. Пожалуйста, попробуйте позже.")
        await state.clear()
        return

    await state.update_data(current_step=step_name)
    fsm_data = await state.get_data()
    question_text = format_response_with_inflection(step_config.get("question"), fsm_data.get("user_answers", {}))
        
    await message.answer(question_text)


async def _finish_fsm(message: types.Message, state: FSMContext):
    """Завершает FSM, обрабатывает данные и сохраняет в БД."""
    fsm_data = await state.get_data()
    user_answers = fsm_data.get("user_answers", {})

    await save_user_details(telegram_id=message.from_user.id, data=user_answers)
    await set_onboarding_completed(message.from_user.id)
    logging.info(f"Онбординг для пользователя {message.from_user.id} завершен и данные сохранены в профиль.")
    
    processed_data = process_final_data(user_answers)
    final_template = FSM_CONFIG.get("final_message_template", "Спасибо!")
    final_text = format_response_with_inflection(final_template, processed_data)

    post_action = fsm_data.get("post_onboarding_action")
    if post_action == "start_booking":
        await message.answer(final_text)
        logging.info(f"Выполняем отложенное действие для {message.from_user.id}: запуск бронирования.")
        await state.clear()
        await booking_handlers.start_booking_scenario(message, state)
    else:
        booking_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выбрать время урока", callback_data="start_booking")]
        ])
        await message.answer(final_text, reply_markup=booking_keyboard)
        await state.clear()


@router.callback_query(F.data.startswith("confirm_layout:"))
async def process_layout_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение коррекции раскладки."""
    fsm_data = await state.get_data()
    action = callback.data.split(":")[1]
    
    answers = fsm_data.get("user_answers", {})
    target_key = fsm_data.get("target_data_key")

    if action == "yes":
        final_input = fsm_data.get("suggested_input")
        await callback.message.edit_text(f"Отлично! Записал: {final_input.capitalize()}.")
    else: # "no"
        final_input = fsm_data.get("original_input")
        await callback.message.edit_text(f"Хорошо, оставил ваш вариант: {final_input}.")

    if target_key:
        answers[target_key] = final_input
    
    await state.update_data(user_answers=answers, original_input=None, suggested_input=None, target_data_key=None)
    
    current_step_config = FSM_CONFIG.get("states", {}).get(fsm_data.get("current_step"), {})
    next_step_name = current_step_config.get("next_state")
    if next_step_name:
        await _ask_next_question(callback.message, state, next_step_name)
    else:
        await _finish_fsm(callback.message, state)
    await callback.answer()


@router.message(GenericFSM.InProgress)
async def handle_fsm_step(message: types.Message, state: FSMContext):
    """
    Обрабатывает ответ пользователя на ЛЮБОМ шаге сценария.
    Это единая точка входа для всех ответов в FSM.
    """
    user_text = message.text.strip()
    fsm_data = await state.get_data()
    current_step_name = fsm_data.get("current_step")

    if not current_step_name:
        logging.warning(f"Получен ответ от {message.from_user.id}, но текущий шаг FSM не определен.")
        return

    current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name)

    if not current_step_config:
        # Обработка ошибки, если шаг не найден в конфигурации
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

    # Сохранение данных
    data_key = current_step_config["data_key"]
    value_to_store = int(user_text) if validation_type == "digits" else user_text
    
    current_answers = fsm_data.get("user_answers", {})
    current_answers[data_key] = value_to_store
    await state.update_data(user_answers=current_answers)

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
            await set_onboarding_completed(message.from_user.id)
            await save_user_details(telegram_id=message.from_user.id, data=current_answers)
            await state.clear()
            return
        elif age > 17:
            response_text = "Здорово! В таком возрасте мы бы уже рекомендовали взрослые курсы для достижения максимального результата. У нас таких, к сожалению, нет, но мы уверены, что вы найдете отличный вариант!"
            await message.answer(response_text)
            await set_onboarding_completed(message.from_user.id)
            await save_user_details(telegram_id=message.from_user.id, data=current_answers)
            await state.clear()
            return
    # Переход к следующему шагу
    next_step_name = current_step_config.get("next_state")
    if next_step_name:
        await _ask_next_question(message, state, next_step_name)
    else:
        await _finish_fsm(message, state)

