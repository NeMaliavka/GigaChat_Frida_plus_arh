# app/handlers/sales_funnel.py

import logging
from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

# --- 1. Импорт ключевых сценариев, которые мы будем запускать ---
from app.handlers.onboarding_handlers import start_fsm_scenario
from app.handlers.cancellation_handlers import start_cancellation_flow
from app.handlers.reschedule_handlers import initiate_reschedule_from_text
from app.handlers import booking_handlers, check_booking_handlers 

# --- 2. Импорт сервисов и утилит ---
# Сервисы для работы с БД и AI
from app.db.database import get_or_create_user, save_history, load_history, increment_irrelevant_count, block_user
from app.core.template_service import find_template_by_keywords, build_template_response
from app.core.llm_service import get_llm_response, is_query_relevant_ai
# Сервис для семантического распознавания намерений (интентов)
from app.services.intent_recognizer import intent_recognizer_service
# Утилиты для отправки уведомлений администраторам
from app.core.admin_notifications import notify_admin_of_request, notify_admin_on_error, notify_admin_of_block


router = Router()

# Лимит нерелевантных вопросов перед блокировкой
IRRELEVANT_QUERY_LIMIT = 3

@router.message(F.text, ~CommandStart())
async def handle_any_text(message: types.Message, state: FSMContext):
    """
    Главный диспетчер текстовых сообщений.
    Реализует воронку: Семантический поиск -> Онбординг -> Шаблоны -> AI.
    Отвечает за модерацию и обработку ошибок.
    """
    # Загружаем историю в самом начале, чтобы она была доступна в случае ошибки
    history = await load_history(str(message.from_user.id))
    try:
        # --- ПОДГОТОВКА И ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ ---
        user = await get_or_create_user(message.from_user.id, message.from_user.username)

        # Если пользователь заблокирован, прекращаем обработку
        if user.is_blocked:
            logging.warning(f"Получено сообщение от заблокированного пользователя {user.id}. Игнорируется.")
            return

        # Сохраняем новое сообщение в историю и загружаем её для передачи в AI
        await save_history(str(user.id), "user", message.text.strip())
        #history = await load_history(str(user.id))
        user_text_lower = message.text.strip().lower()
        # --- ОНБОРДИНГ ДЛЯ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ ---
        if not user.onboarding_completed:
            logging.info(f"Пользователь {user.id} не прошел онбординг. Запускаем FSM-сценарий.")
            # Определяем намерение пользователя, чтобы не терять его
            initial_intent = intent_recognizer_service.get_intent(user_text_lower)
            if initial_intent == "booking_request":
                # Сохраняем намерение в FSM, чтобы выполнить его после онбординга
                await state.update_data(post_onboarding_action="start_booking")
                logging.info(f"Для пользователя {user.id} установлено действие после онбординга: 'start_booking'")

            # Запускаем сценарий знакомства
            await start_fsm_scenario(message, state)
            return


        # --- СЕМАНТИЧЕСКОЕ РАСПОЗНАВАНИЕ ИНТЕНТА (ВЫСОКИЙ ПРИОРИТЕТ) ---
        # Вместо жесткого перебора ключевых слов, используем семантический поиск.
        detected_intent = intent_recognizer_service.get_intent(user_text_lower)

        # Если интент уверенно распознан, запускаем соответствующий сценарий
        if detected_intent:
            match detected_intent:
                case "cancellation":
                    logging.info("Обнаружен интент 'отмена' через семантический поиск.")
                    await start_cancellation_flow(message, state)
                    return
                case "reschedule":
                    logging.info("Обнаружен интент 'перенос' через семантический поиск.")
                    await initiate_reschedule_from_text(message, state)
                    return
                case "booking_request":
                    logging.info("Обнаружен интент 'запись на урок' через семантический поиск.")
                    await booking_handlers.start_booking_scenario(message, state)
                    return
                case "human_operator":
                    logging.info("Обнаружен интент 'позвать оператора' через семантический поиск.")
                    await message.answer("Понимаю, сейчас позову менеджера. Он скоро свяжется с вами прямо здесь, в Telegram.")
                    await notify_admin_of_request(bot=message.bot, user=message.from_user, request_text=message.text)
                    return

        # Поиск ответа в готовых шаблонах (для простых вопросов, где не нужна семантика)
        key, template = find_template_by_keywords(user_text_lower)
        if template:
            logging.info(f"Найден шаблон '{key}' для запроса от {user.id}.")
            user_details = user.user_data or {}
            user_context_data = {'parent_name':user_details.get('parent_name', message.from_user.first_name), 'child_name':user_details.get('child_name', "ваш ребенок")}
            response = await build_template_response(template, history, user_context_data)
            await message.answer(response)
            return
        
        # Проверка релевантности запроса с помощью AI-фильтра
        if not await is_query_relevant_ai(message.text, history):
            remaining_attempts = await increment_irrelevant_count(user.id)
            if remaining_attempts >= IRRELEVANT_QUERY_LIMIT:
                await block_user(user.id)
                block_reason = "Превышен лимит нерелевантных запросов."
                await message.answer(f"Общение временно приостановлено. Причина: {block_reason}\n\nЯ уже позвал менеджера, он разберется в ситуации и скоро с вами свяжется.")
                await notify_admin_of_block(bot=message.bot, user=message.from_user, reason=block_reason, history=history)
            else:
                attempts_left = IRRELEVANT_QUERY_LIMIT - remaining_attempts
                await message.answer(f"Я не совсем понимаю ваш вопрос, он не относится к работе нашей школы. Пожалуйста, будьте внимательнее. (Осталось попыток: {attempts_left})")
            return

        # Показываем статус "печатает...", чтобы улучшить UX
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

        

        # 4.3. Если шаблона нет, обращаемся к основной LLM
        logging.info(f"Шаблон не найден. Передаем запрос от {user.id} в основную LLM.")
        llm_response = await get_llm_response(message.text, history)

        # 4.4. Парсинг ответа от LLM и выполнение команд
        if "[START_BOOKING]" in llm_response or "[START_ENROLLMENT]" in llm_response:
            logging.info(f"LLM вернул команду на бронирование для {user.id}.")
            await booking_handlers.start_booking_scenario(message, state)
        elif "CHECK_BOOKING" in llm_response:
            logging.info(f"LLM инициировал проверку записи для {message.from_user.id}.")
            await check_booking_handlers.start_check_booking_flow(message, state)
        elif "[CANCEL_BOOKING]" in llm_response:
            logging.info(f"LLM вернул команду на отмену для {user.id}.")
            await start_cancellation_flow(message, state)
        elif "[RESCHEDULE_BOOKING]" in llm_response:
            logging.info(f"LLM вернул команду на перенос для {user.id}.")
            await initiate_reschedule_from_text(message, state)
        else:
            # Если команд нет, просто отправляем текст от AI
            await message.answer(llm_response)

    except Exception as e:
        logging.error(f"Критическая ошибка в 'handle_any_text' при обработке сообщения от {message.from_user.id}: {e}", exc_info=True)
        #history_for_admin = await load_history(str(message.from_user.id))
        await notify_admin_on_error(
            bot=message.bot,
            user_id=message.from_user.id,
            username=message.from_user.username,
            error_description=str(e),
            history=history
        )
        await message.answer("Произошла непредвиденная ошибка. Я уже сообщил о ней нашей команде. Пожалуйста, попробуйте повторить ваш запрос чуть позже.")
