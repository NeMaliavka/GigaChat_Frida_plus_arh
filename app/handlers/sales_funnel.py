# app/handlers/sales_funnel.py

import logging
from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- 1. Импорт ключевых сценариев, которые мы будем запускать ---
from app.handlers.onboarding_handlers import start_fsm_scenario
from app.handlers.cancellation_handlers import start_cancellation_flow
from app.handlers import reschedule_handlers
from app.handlers import check_booking_handlers
from app.handlers import booking_handlers

# --- 2. Импорт сервисов и утилит ---
from app.db.database import get_or_create_user, save_history, load_history, get_all_active_lessons, increment_irrelevant_count, block_user
from app.core.template_service import find_template_by_keywords, build_template_response
from app.core.llm_service import get_llm_response, is_query_relevant_ai
from app.services.intent_recognizer import intent_recognizer_service
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
    history = await load_history(str(message.from_user.id))
    try:
        user = await get_or_create_user(message.from_user.id, message.from_user.username)

        if user.is_blocked:
            logging.warning(f"Получено сообщение от заблокированного пользователя {user.id}. Игнорируется.")
            return

        await save_history(str(user.id), "user", message.text.strip())
        user_text_lower = message.text.strip().lower()

        if not user.onboarding_completed:
            logging.info(f"Пользователь {user.id} не прошел онбординг. Запускаем FSM-сценарий.")
            initial_intent = intent_recognizer_service.get_intent(user_text_lower)
            if initial_intent == "booking_request":
                await state.update_data(post_onboarding_action="start_booking")
            await start_fsm_scenario(message, state)
            return

        # --- СЕМАНТИЧЕСКОЕ РАСПОЗНАВАНИЕ ИНТЕНТА (ВЫСОКИЙ ПРИОРИТЕТ) ---
        detected_intent = intent_recognizer_service.get_intent(user_text_lower)

        if detected_intent:
            logging.info(f"Обнаружен интент '{detected_intent}' для пользователя {user.id}.")
            active_lessons = await get_all_active_lessons(user.id)

            match detected_intent:
                # --- Функциональные интенты (бронирование, отмена и т.д.) ---
                case "check_booking":
                    await check_booking_handlers.start_check_booking_flow(message, state)
                case "cancellation":
                    if not active_lessons:
                        await message.answer("Я бы рад отменить, но у вас нет активных записей.")
                    else:
                        await start_cancellation_flow(message, state)
                case "reschedule":
                    if not active_lessons:
                        await message.answer("Я не нашел записей для переноса.")
                    else:
                        await reschedule_handlers.start_reschedule_flow(message, state)
                case "booking_request":
                    if active_lessons:
                        builder = InlineKeyboardBuilder()
                        builder.button(text="Перенести существующую", callback_data="initiate_reschedule")
                        builder.button(text="Записать еще одного ребенка", callback_data="start_booking_additional")
                        builder.adjust(1)
                        await message.answer("Я вижу, у вас уже есть активная запись. Что вы хотите сделать?", reply_markup=builder.as_markup())
                    else:
                        logging.info(f"Для пользователя {user.id} запускается онбординг перед новой записью.")
                        await state.update_data(post_onboarding_action="start_booking")
                        await start_fsm_scenario(message, state)
                case "human_operator":
                    await message.answer("Понимаю, сейчас позову менеджера.")
                    await notify_admin_of_request(bot=message.bot, user=message.from_user, request_text=message.text)
                
                case "price_request" | "greeting" | "social_status_info":
                    key, template = find_template_by_keywords(user_text_lower)
                    if template:
                        user_details = user.user_data or {}
                        # Формируем контекст для персонализации ответа
                        user_context_data = {
                            'parent_name': user_details.get('parent_name', message.from_user.first_name),
                            'child_name': user_details.get('child_name', "ваш ребенок")
                        }
                        # Собираем и отправляем ответ из шаблона
                        response = await build_template_response(template, history, user_context_data)
                        await message.answer(response)
                    else:
                        # Если интент есть, а шаблона нет - это повод позвать человека
                        await message.answer("Я понял ваш вопрос, но не смог найти точный ответ. Сейчас позову менеджера.")
                        await notify_admin_of_request(bot=message.bot, user=message.from_user, request_text=message.text)

            return
        
        # --- Если интент не распознан, передаем в LLM ---
        logging.info(f"Интент не распознан. Передаем запрос от {user.id} в основную LLM.")
        
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

        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        llm_response = await get_llm_response(message.text, history)
        await message.answer(llm_response)

    except Exception as e:
        logging.error(f"Критическая ошибка в 'handle_any_text' при обработке сообщения от {message.from_user.id}: {e}", exc_info=True)
        await notify_admin_on_error(
            bot=message.bot,
            user_id=message.from_user.id,
            username=message.from_user.username,
            error_description=str(e),
            history=history
        )
        await message.answer("Произошла непредвиденная ошибка. Я уже сообщил о ней нашей команде. Пожалуйста, попробуйте повторить ваш запрос чуть позже.")
