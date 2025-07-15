# app/handlers/sales_funnel.py

import logging
from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

# --- 1. Импорт ключевых сценариев ---
# Сценарий сбора данных о новом пользователе (анкетирование)
from app.handlers.onboarding_handlers import start_fsm_scenario
# Сценарий отмены существующей записи
from app.handlers.cancellation_handlers import start_cancellation_flow
# Сценарий для начала бронирования (вызывается командой от AI)
from app.handlers import booking_handlers 

# --- 2. Импорт сервисов и утилит ---
# Сервисы для работы с БД, шаблонами и AI
# Предполагается, что эти файлы существуют и содержат необходимые функции
from app.db.database import get_or_create_user, save_history, load_history, increment_irrelevant_count, block_user
from app.core.template_service import find_template_by_keywords, build_template_response
from app.core.llm_service import get_llm_response, is_query_relevant_ai
# Утилиты для загрузки ключевых слов и отправки уведомлений администраторам
from app.utils.loaders import load_keywords_from_yaml
from app.core.admin_notifications import notify_admin_of_request, notify_admin_on_error, notify_admin_of_block

router = Router()

# --- 3. Константы и начальная загрузка ---
# Лимит нерелевантных вопросов перед блокировкой
IRRELEVANT_QUERY_LIMIT = 3
# Загрузка ключевых слов из YAML-файла при старте бота
ALL_KEYWORDS = load_keywords_from_yaml()
CANCELLATION_KEYWORDS = ALL_KEYWORDS.get('cancellation', [])
HUMAN_OPERATOR_KEYWORDS = ALL_KEYWORDS.get('human_operator', [])


@router.message(F.text, ~CommandStart())
async def handle_any_text(message: types.Message, state: FSMContext):
    """
    Главный диспетчер текстовых сообщений.
    Реализует воронку: Ключевые слова -> Онбординг -> Шаблоны -> AI.
    Отвечает за модерацию и обработку ошибок.
    """
    try:
        # --- ШАГ I: ПОДГОТОВКА И ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ ---
        user = await get_or_create_user(message.from_user.id, message.from_user.username)
        
        # Если пользователь заблокирован, прекращаем обработку
        if user.is_blocked:
            logging.warning(f"Получено сообщение от заблокированного пользователя {user.id}. Игнорируется.")
            return

        # Сохраняем новое сообщение в историю
        await save_history(str(user.id), "user", message.text.strip())
        # Загружаем обновленную историю для передачи в AI
        history = await load_history(str(user.id))
        user_text_lower = message.text.strip().lower()

        # --- ШАГ II: БЫСТРЫЕ ДЕЙСТВИЯ ПО КЛЮЧЕВЫМ СЛОВАМ (ВЫСОКИЙ ПРИОРИТЕТ) ---
        # 1. Запрос на отмену
        if CANCELLATION_KEYWORDS and any(keyword in user_text_lower for keyword in CANCELLATION_KEYWORDS):
            logging.info(f"Обнаружен интент 'отмена' от {user.id}. Запуск сценария отмены.")
            await start_cancellation_flow(message, state)
            return

        # 2. Запрос на вызов менеджера
        if HUMAN_OPERATOR_KEYWORDS and any(keyword in user_text_lower for keyword in HUMAN_OPERATOR_KEYWORDS):
            logging.info(f"Обнаружен интент 'позвать оператора' от {user.id}.")
            await message.answer("Понимаю, сейчас позову менеджера. Он скоро свяжется с вами прямо здесь, в Telegram.")
            await notify_admin_of_request(bot=message.bot, user=message.from_user, request_text=message.text)
            return
            
        # --- ШАГ III: ОНБОРДИНГ ДЛЯ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ ---
        # Если пользователь еще не заполнил анкету, запускаем сценарий
        if not user.onboarding_completed:
            logging.info(f"Пользователь {user.id} не прошел онбординг. Запускаем FSM-сценарий.")
            await start_fsm_scenario(message, state)
            return

        # --- ШАГ IV: ОБРАБОТКА ВОПРОСОВ (ШАБЛОНЫ, AI, МОДЕРАЦИЯ) ---
        
        # 4.1. Проверка релевантности запроса
        if not await is_query_relevant_ai(message.text, history):
            remaining_attempts = await increment_irrelevant_count(user.id)
            
            if remaining_attempts >= IRRELEVANT_QUERY_LIMIT:
                await block_user(user.id)
                block_reason = "Превышен лимит нерелевантных запросов."
                await message.answer(f"Общение временно приостановлено. Причина: {block_reason}\n\nЯ уже позвал менеджера, он разберется в ситуации и скоро с вами свяжется.")
                await notify_admin_of_block(bot=message.bot, user=message.from_user, reason=block_reason, history=history)
                return
            else:
                attempts_left = IRRELEVANT_QUERY_LIMIT - remaining_attempts
                await message.answer(f"Я не совсем понимаю ваш вопрос, он не относится к работе нашей школы. Пожалуйста, будьте внимательнее. (Осталось попыток: {attempts_left})")
                return
        
        # Показываем статус "печатает...", чтобы улучшить UX
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # 4.2. Поиск ответа в готовых шаблонах
        key, template = find_template_by_keywords(user_text_lower)
        if template:
            logging.info(f"Найден шаблон '{key}' для запроса от {user.id}.")
            # Собираем данные о пользователе для персонализации ответа
            user_context_data = {'parent_name': user.parent_name or message.from_user.first_name, 'child_name': user.child_name or "ваш ребенок"}
            response = await build_template_response(template, history, user_context_data)
            await message.answer(response)
            return

        # 4.3. Если шаблона нет, обращаемся к LLM
        logging.info(f"Шаблон не найден. Передаем запрос от {user.id} в LLM.")
        llm_response = await get_llm_response(message.text, history)
        
        # 4.4. Парсинг ответа от LLM и выполнение команд
        if "[START_BOOKING]" in llm_response or "[START_ENROLLMENT]" in llm_response:
            logging.info(f"LLM вернул команду на бронирование для {user.id}.")
            await booking_handlers.start_booking_scenario(message, state)
        elif "[CANCEL_BOOKING]" in llm_response:
            logging.info(f"LLM вернул команду на отмену для {user.id}.")
            await start_cancellation_flow(message, state)
        else:
            # Если команд нет, просто отправляем текст от AI
            await message.answer(llm_response)

    except Exception as e:
        logging.error(f"Критическая ошибка в 'handle_any_text' при обработке сообщения от {message.from_user.id}: {e}", exc_info=True)
        # Сначала сохраняем проблемное сообщение
        await save_history(str(message.from_user.id), "user", message.text.strip())
        # Затем загружаем полную историю для админа
        history_for_admin = await load_history(str(message.from_user.id))

        await notify_admin_on_error(
            bot=message.bot,
            user_id=message.from_user.id,
            username=message.from_user.username,
            error_description=str(e),
            history=history_for_admin
        )
        
        await message.answer("Произошла непредвиденная ошибка. Я уже сообщил о ней нашей команде. Пожалуйста, попробуйте повторить ваш запрос чуть позже.")