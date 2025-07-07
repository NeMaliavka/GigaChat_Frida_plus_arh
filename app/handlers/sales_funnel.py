import logging
import json
from pathlib import Path
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

# Импортируем все необходимые сервисы и функции
from app.core.template_service import find_template, choose_variant
from app.core.llm_service import get_llm_response, is_query_relevant_ai, correct_user_query
from app.core.business_logic import process_final_data
from app.core.admin_notifications import notify_admin_on_error
from app.db.database import get_or_create_user, save_user_details, save_history, load_history, set_onboarding_completed
from app.keyboards.inline import get_enroll_keyboard

router = Router()

# --- FSM Сценарий ---
FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"
try:
    with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
        FSM_CONFIG = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"Критическая ошибка: не удалось загрузить FSM-сценарий. {e}")
    FSM_CONFIG = {}

class GenericFSM(StatesGroup):
    InProgress = State()

async def start_fsm_scenario(message: types.Message, state: FSMContext):
    """
    Универсальная функция для запуска FSM-сценария.
    """
    if not FSM_CONFIG:
        await message.answer("Извините, функция записи временно недоступна.")
        return
    
    initial_step = FSM_CONFIG.get("initial_state")
    logging.info(f"Запускаем сценарий онбординга '{FSM_CONFIG.get('scenario_name', 'N/A')}' для пользователя {message.from_user.id}")
    
    await state.set_state(GenericFSM.InProgress)
    await state.update_data(current_step=initial_step)
    
    intro_text = FSM_CONFIG.get("onboarding_intro", "Здравствуйте! Давайте познакомимся!\n\n")
    start_question = FSM_CONFIG.get("start_message", "Как я могу к вам обращаться?")
    
    full_start_text = intro_text + start_question
    await message.answer(full_start_text)

# --- ЕДИНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ ТЕКСТОВЫХ СООБЩЕНИЙ ---
@router.message(F.text)
async def handle_any_text(message: types.Message, state: FSMContext):
    user_id_str = str(message.from_user.id)
    user_text = message.text

    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    await save_history(user_id_str, "user", user_text)

    current_fsm_state = await state.get_state()

    # Проактивный онбординг для новых пользователей
    if not user.onboarding_completed and current_fsm_state is None:
        await start_fsm_scenario(message, state)
        return

    # --- НОВЫЙ, НАДЕЖНЫЙ FSM-ДВИЖОК ---
    if current_fsm_state == GenericFSM.InProgress.state:
        fsm_data = await state.get_data()
        current_step_name = fsm_data.get("current_step")
        current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name)

        if not current_step_config:
            # Обработка ошибки конфигурации с вызовом администратора
            error_text = f"Ошибка в конфигурации сценария. Не найден шаг: {current_step_name}"
            history_for_admin = await load_history(user_id_str, limit=10)
            await notify_admin_on_error(
                bot=message.bot,
                user_id=message.from_user.id,
                username=message.from_user.username,
                error_description=error_text,
                history=history_for_admin
            )
            await message.answer("Ой, кажется, у меня возникла небольшая техническая заминка. Уже позвал на помощь живого администратора, он скоро подключится!")
            await state.clear()
            return

        # Валидация данных для текущего шага
        if current_step_config.get("validation") == "digits" and not user_text.isdigit():
            await message.answer(current_step_config.get("error_message", "Неверный формат."))
            return

        # Сохраняем ответ пользователя
        fsm_data[current_step_config["data_key"]] = user_text
        
        # Получаем ШАБЛОН ОТВЕТА, который привязан к ТЕКУЩЕМУ шагу
        response_template = current_step_config.get("question")
        if response_template:
            # Отправляем следующий вопрос
            await message.answer(response_template.format(**fsm_data, previous_answer=user_text))

        next_step_name = current_step_config.get("next_state")
        
        if next_step_name:
            # Если есть следующий шаг, просто обновляем состояние
            fsm_data["current_step"] = next_step_name
            await state.set_data(fsm_data)
        else:
            # Финал сценария: нет следующего шага
            await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
            await set_onboarding_completed(message.from_user.id)
            logging.info(f"Онбординг для пользователя {user_id_str} успешно завершен.")

            processed_data = process_final_data(fsm_data)
            
            # Проверяем, вернул ли "движок правил" готовое сообщение
            if "final_response" in processed_data:
                await message.answer(processed_data["final_response"])
            else:
                # Если нет, используем стандартный шаблон с предложением
                final_text = FSM_CONFIG["final_message_template"].format(**processed_data)
                await message.answer(final_text, reply_markup=get_enroll_keyboard())
            
            await state.clear()
        return

    # --- ЛОГИКА "ФРИДЫ" (для пользователей, которые уже прошли знакомство) ---
    history = await load_history(user_id_str)
    response_text = ""

    # Определяем персональный контекст для пользователя
    user_data = user.user_data or {}
    child_age_str = user_data.get("child_age", "0")
    child_age = int(child_age_str) if child_age_str.isdigit() else 0

    if 9 <= child_age <= 13: context_key = "course_junior"
    elif 14 <= child_age <= 17: context_key = "course_senior"
    else: context_key = "default"
    
    _template_key, template_value = find_template(user_text, context_key=context_key)
    
    if template_value:
        await state.update_data(offtopic_count=0)
        response_text = choose_variant(template_value)
    else:
        corrected_text = await correct_user_query(user_text)
        if await is_query_relevant_ai(corrected_text, history):
            await state.update_data(offtopic_count=0)
            response_text = await get_llm_response(question=corrected_text, history=history, context_key=context_key)
        else:
            # Обработка нерелевантного запроса
            data = await state.get_data()
            offtopic_count = data.get("offtopic_count", 0) + 1
            await state.update_data(offtopic_count=offtopic_count)

            if offtopic_count >= 3:
                logging.warning(f"Пользователь {user_id_str} заблокирован после 3 нерелевантных запросов.")
                await message.answer("Я вижу, что вас интересуют вопросы, не связанные с нашей школой. Чтобы не тратить ваше и мое время, я вынужден временно приостановить диалог.")
            else:
                await message.answer(f"Это интересный вопрос, но он не относится к работе нашей школы. Пожалуйста, задавайте вопросы по теме. (Осталось попыток: {3 - offtopic_count})")
    
    if response_text:
        await message.answer(response_text)
        await save_history(user_id_str, "assistant", response_text)
