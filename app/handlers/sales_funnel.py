import logging
import json
import re
import locale

from pathlib import Path
from html import escape
from datetime import datetime, timedelta

from zoneinfo import ZoneInfo 

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart

# Импортируем все необходимые сервисы и функции
from app.core.template_service import find_template_by_keywords, build_template_response
from app.core.llm_service import get_llm_response, is_query_relevant_ai, correct_user_query
from app.core.business_logic import process_final_data
from app.core.admin_notifications import notify_admin_on_error, notify_admin_on_suspicious_activity
from app.db.database import get_or_create_user, save_user_details, save_history, load_history, set_onboarding_completed, get_last_message_time
from app.services.bitrix_service import get_free_slots, book_lesson
from app.config import TEACHER_IDS # Импортируем ID учителей из конфига

# --- FSM МОДЕЛИ ---

class GenericFSM(StatesGroup):
    InProgress = State()

class WaitlistFSM(StatesGroup):
    waiting_for_contact = State()

class BookingFSM(StatesGroup):
    choosing_date = State()
    choosing_time = State()

# --- УТИЛИТЫ ---

# Импортируем утилиты, обрабатывая возможное их отсутствие
try:
    from app.utils.text_tools import correct_keyboard_layout, is_plausible_name, inflect_name
    MORPHOLOGY_ENABLED = True
except ImportError:
    logging.warning("Утилиты (text_tools.py) не найдены. Расширенные функции будут отключены.")
    MORPHOLOGY_ENABLED = False
    def correct_keyboard_layout(_: str) -> None: return None
    def is_plausible_name(_: str) -> bool: return True
    def inflect_name(name: str, _: str) -> str: return name

# # --- УНИВЕРСАЛЬНАЯ УСТАНОВКА РУССКОЙ ЛОКАЛИ  Не сработали---
# # Пробуем несколько стандартных имен для разных ОС (Windows, Linux, macOS)
# try:
#     locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
# except locale.Error:
#     try:
#         locale.setlocale(locale.LC_TIME, 'russian')
#     except locale.Error:
#         logging.warning("Не удалось установить русскую локаль. Месяцы могут отображаться на английском.")
# # --------------------------------------------------
# --- ИНИЦИАЛИЗАЦИЯ РОУТЕРА И КОНФИГУРАЦИИ ---

router = Router()

FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"
try:
    with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
        FSM_CONFIG = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"Критическая ошибка: не удалось загрузить FSM-сценарий. {e}")
    FSM_CONFIG = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def _format_response_with_inflection(template: str, data: dict) -> str:
    """Форматирует строку, склоняя имена и корректно капитализируя их."""
    if not MORPHOLOGY_ENABLED or not template:
        # Простая обработка для случая, если нет user_data
        return template.format(**data) if template else ""
    
    def repl(match):
        var_name, case = match.groups()
        return inflect_name(data.get(var_name, ""), case)
    
    processed_template = re.sub(r'\{(\w+):(\w+)\}', repl, template)

    final_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            final_data[key] = " ".join(word.capitalize() for word in value.split())
        else:
            final_data[key] = value
            
    return processed_template.format(**final_data)


# --- НОВАЯ ФУНКЦИЯ ДЛЯ РУСИФИКАЦИИ ДАТЫ ---
def format_date_russian(dt: datetime, format_type: str = 'full') -> str:
    """
    Надежно форматирует дату на русском языке, не завися от системной локали.
    """
    months_gent = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    weekdays = [
        "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"
    ]
    
    if format_type == 'full':
        # Формат для кнопок: "11 июля (Пятница)"
        return f"{dt.day} {months_gent[dt.month - 1]} ({weekdays[dt.weekday()]})"
    elif format_type == 'short':
        # Формат для подтверждения: "11 июля в 17:00"
        return f"{dt.day} {months_gent[dt.month - 1]} в {dt.strftime('%H:%M')}"
    return dt.strftime('%Y-%m-%d %H:%M') # Возврат по умолчанию

# --- ХЕНДЛЕРЫ ЛИСТА ОЖИДАНИЯ ---

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
    current_data['waitlist_for_age'] = '<9'
    await save_user_details(telegram_id=user.telegram_id, data=current_data)
    logging.info(f"Пользователь {user.telegram_id} добавлен в лист ожидания: {contact_info}")
    await message.answer("Спасибо! Мы сохранили ваши данные и обязательно с вами свяжемся.")
    await state.clear()

# --- ЛОГИКА ОСНОВНОГО FSM-СЦЕНАРИЯ (ОНБОРДИНГ) ---

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
        if not next_step_config: return
        fsm_data['current_step'] = next_step_name
        await state.set_data(fsm_data)
        next_question = _format_response_with_inflection(next_step_config.get("question"), fsm_data)
        await message.answer(next_question)
    else:
        # Финал сценария
        await set_onboarding_completed(message.from_user.id)
        processed_data = process_final_data(fsm_data)
        final_template = FSM_CONFIG.get("final_message_template", "Спасибо!")
        final_text = _format_response_with_inflection(final_template, processed_data)
        
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
    await state.set_data(fsm_data)
    fsm_data.pop("original_input", None); fsm_data.pop("suggested_input", None)
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

    if MORPHOLOGY_ENABLED and current_step_config.get("needs_layout_correction", False):
        if corrected_text := correct_keyboard_layout(user_text):
            await state.update_data(original_input=user_text, suggested_input=corrected_text, target_data_key=current_step_config["data_key"])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Да, это «{corrected_text.capitalize()}»", callback_data="confirm_layout:yes")], [InlineKeyboardButton(text="Нет, оставить как есть", callback_data="confirm_layout:no")]])
            await message.answer(f"Вы ввели «{escape(user_text)}». Возможно, вы имели в виду «{corrected_text.capitalize()}»?", reply_markup=keyboard)
            return

    validation_type = current_step_config.get("validation")
    is_valid = True
    if MORPHOLOGY_ENABLED and validation_type:
        if validation_type == "name": is_valid = is_plausible_name(user_text)
        elif validation_type == "digits": is_valid = user_text.isdigit()
    
    if not is_valid:
        await message.answer(current_step_config.get("error_message", "Неверный формат."))
        return
    
    data_key = current_step_config["data_key"]
    value_to_store = int(user_text) if validation_type == "digits" else user_text
    fsm_data[data_key] = value_to_store

    if data_key == 'child_age':
        age = value_to_store
        if age < 9:
            response_text = "На данный момент наши курсы рассчитаны на детей от 9 лет, но мы уже активно создаем программу для самых юных программистов!\n\nХотите, мы сообщим вам о запуске в числе первых? Это бесплатно и ни к чему не обязывает."
            buttons = [InlineKeyboardButton(text="Да, сообщите мне!", callback_data="waitlist:join"), InlineKeyboardButton(text="Нет, спасибо", callback_data="waitlist:cancel")]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
            await message.answer(response_text, reply_markup=reply_markup)
            await set_onboarding_completed(message.from_user.id)
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

    await _advance_fsm_step(message, state, fsm_data)

# --- ДИСПЕТЧЕР КОМАНД ОТ LLM ---

async def process_llm_command(command: str, message: types.Message, state: FSMContext) -> bool:
    """
    Обрабатывает специальные команды, полученные от LLM.
    Возвращает True, если команда была распознана и обработана.
    """
    # Проверяем вхождение, чтобы быть устойчивыми к возможному "мусору" от LLM
    if "[START_ENROLLMENT]" in command:
        logging.info(f"LLM инициировал запуск сценария записи для пользователя {message.from_user.id}")
        await start_fsm_scenario(message, state)
        return True
        
    return False

# --- ЕДИНЫЙ ОБРАБОТЧИК ДЛЯ ВСЕХ ТЕКСТОВЫХ СООБЩЕНИЙ ---

@router.message(F.text, ~CommandStart())
async def handle_any_text(message: types.Message, state: FSMContext):
    user_id_str = str(message.from_user.id)
    user_text = message.text.strip()
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    await save_history(user_id_str, "user", user_text)
    
    if not user.onboarding_completed:
        await start_fsm_scenario(message, state)
        return

    last_msg_time = await get_last_message_time(user.id)
    if last_msg_time and (datetime.now() - last_msg_time > timedelta(hours=7)):
        parent_name = (user.user_data or {}).get('parent_name', 'Гость')
        capitalized_name = " ".join(word.capitalize() for word in parent_name.split())
        await message.answer(f"С возвращением, {capitalized_name}! Рад вас снова видеть.\nЧем могу помочь сегодня?")

    history = await load_history(user_id_str)
    response_text = None

    template_key, template_data = find_template_by_keywords(user_text)
    if template_data:
        response_text = await build_template_response(template_data, history, user.user_data or {})
    else:
        corrected_text = await correct_user_query(user_text)
        if await is_query_relevant_ai(corrected_text, history):
            response_text = await get_llm_response(question=corrected_text, history=history, context_key="default")
        else:
            data = await state.get_data()
            offtopic_count = data.get("offtopic_count", 0) + 1
            await state.update_data(offtopic_count=offtopic_count)
            if offtopic_count >= 3:
                await notify_admin_on_suspicious_activity(bot=message.bot, user_id=user.id, username=user.username, history=history)
                response_text = "Я вижу, что вас интересуют вопросы, не связанные с нашей школой. Вынужден приостановить диалог."
            else:
                response_text = f"Это интересный вопрос, но он не относится к работе нашей школы. (Осталось попыток: {3 - offtopic_count})"
    
    if response_text:
        # Добавляем лог, чтобы видеть "сырой" ответ от LLM
        logging.info(f"Сырой ответ от LLM/шаблонизатора: '{response_text}'")
        
        command_processed = await process_llm_command(response_text, message, state)
        if not command_processed:
            await message.answer(response_text)
            await save_history(user_id_str, "assistant", response_text)

# --- ХЕНДЛЕРЫ ПРОЦЕССА БРОНИРОВАНИЯ ---

@router.callback_query(F.data == "start_booking")
async def handle_start_booking(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отлично! Загружаю доступное расписание...")
    try:
        portal_tz = ZoneInfo("Europe/Moscow")
        now = datetime.now(portal_tz)
        from_date = now
        to_date = now + timedelta(days=7)
        free_slots_by_date = await get_free_slots(from_date=from_date, to_date=to_date, user_ids=TEACHER_IDS)
        
        if not free_slots_by_date:
            await callback.message.edit_text("К сожалению, на ближайшую неделю свободных окон нет.")
            return

        await state.update_data(free_slots=free_slots_by_date)
        
        date_buttons = [[InlineKeyboardButton(text=format_date_russian(datetime.strptime(date_str, '%Y-%m-%d'), 'full'), callback_data=f"book_date:{date_str}")] for date_str in sorted(free_slots_by_date.keys())]
        keyboard = InlineKeyboardMarkup(inline_keyboard=date_buttons)

        # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
        # 1. Сначала устанавливаем состояние
        await state.set_state(BookingFSM.choosing_date)
        # 2. Затем отправляем сообщение с кнопками
        await callback.message.edit_text("Выберите удобный день:", reply_markup=keyboard)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    except Exception as e:
        logging.error(f"Критическая ошибка в handle_start_booking: {e}", exc_info=True)
        await callback.message.edit_text("Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")
    finally:
        await callback.answer()

@router.callback_query(BookingFSM.choosing_date, F.data.startswith("book_date:"))
async def handle_date_selection(callback: types.CallbackQuery, state: FSMContext):
    selected_date = callback.data.split(":")[1]
    fsm_data = await state.get_data()
    slots_for_date = fsm_data.get('free_slots', {}).get(selected_date, [])
    
    unique_times = sorted(list(set(s['time'] for s in slots_for_date)))
    
    time_buttons = [InlineKeyboardButton(text=time_str, callback_data=f"book_time:{selected_date}T{time_str}") for time_str in unique_times]
    
    grouped_buttons = [time_buttons[i:i + 3] for i in range(0, len(time_buttons), 3)]
    grouped_buttons.append([InlineKeyboardButton(text="⬅️ Назад к выбору дня", callback_data="start_booking")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=grouped_buttons)
    formatted_date = format_date_russian(datetime.strptime(selected_date, '%Y-%m-%d'), 'full')
    
    await callback.message.edit_text(f"Вы выбрали {formatted_date}.\nТеперь выберите удобное время:", reply_markup=keyboard)
    await state.set_state(BookingFSM.choosing_time)
    await callback.answer()

@router.callback_query(BookingFSM.choosing_time, F.data.startswith("book_time:"))
async def handle_time_selection(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Секундочку, сверяюсь с расписанием...")
    datetime_str = callback.data.split(":", 1)[1]
    naive_start_time = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')
    portal_tz = ZoneInfo("Europe/Moscow")
    start_time = naive_start_time.replace(tzinfo=portal_tz)
    
    fsm_data = await state.get_data()
    user_db = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    client_data = user_db.user_data or {}
    client_data['username'] = callback.from_user.username
    
    selected_date_str = start_time.strftime('%Y-%m-%d')
    selected_time_str = start_time.strftime('%H:%M')
    
    available_teachers_ids = [s['user_id'] for s in fsm_data.get('free_slots', {}).get(selected_date_str, []) if s['time'] == selected_time_str]
    
    created_entity_id, teacher_name = None, None
    for teacher_id in available_teachers_ids:
        logging.info(f"Пытаюсь забронировать слот {start_time} у преподавателя ID: {teacher_id}")
        temp_id, temp_name = await book_lesson(user_id=teacher_id, start_time=start_time, duration_minutes=60, client_data=client_data)
        if temp_id:
            created_entity_id, teacher_name = temp_id, temp_name
            logging.info(f"Успешное бронирование у преподавателя ID: {teacher_id}")
            break
        else:
            logging.warning(f"Не удалось забронировать у преподавателя ID: {teacher_id}, пробую следующего.")
            
    if created_entity_id:
        confirmation_date = format_date_russian(start_time, 'short')
        await callback.message.edit_text(f"Отлично! ✅\n\nВы успешно записаны на пробный урок {confirmation_date}. Вся информация передана вашему преподавателю: {teacher_name}. До встречи!", reply_markup=None)
        await state.clear()
    else:
        await callback.message.edit_text("😔 Ой, кажется, это время только что полностью заняли. Пожалуйста, выберите другое.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Выбрать другой день", callback_data="start_booking")]]))
    
    await callback.answer()
