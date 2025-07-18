import logging
from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.handlers.onboarding_handlers import start_fsm_scenario
from app.handlers.cancellation_handlers import start_cancellation_flow
from app.handlers import reschedule_handlers, check_booking_handlers, booking_handlers
from app.handlers.cancellation_handlers import CancelCallbackFactory
from app.db.database import get_or_create_user, save_history, load_history, get_all_active_lessons, increment_irrelevant_count, block_user
from app.core.template_service import find_template_by_keywords, build_template_response, TEMPLATES
from app.core.llm_service import get_llm_response, is_query_relevant_ai
from app.services.intent_recognizer import intent_recognizer_service
from app.core.admin_notifications import notify_admin_of_request, notify_admin_on_error, notify_admin_of_block
from app.utils.text_tools import correct_keyboard_layout
from app.utils.formatters import format_date_russian

from app.handlers.utils.keyboards import get_existing_user_menu, get_faq_menu

from aiogram.exceptions import TelegramBadRequest

from aiogram.filters import Command

router = Router()
IRRELEVANT_QUERY_LIMIT = 3
# =============================================================================
# Обработчики команд из кнопки "Меню"
# =============================================================================
from aiogram.filters import Command

@router.message(Command("booking"))
async def handle_booking_command(message: types.Message, state: FSMContext):
    """Обрабатывает команду /booking из меню - запускает сценарий записи."""
    logging.info(f"Пользователь {message.from_user.id} вызвал команду /booking.")
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    if not user.onboarding_completed:
        await message.answer("Отлично, давайте познакомимся! Задам всего пару вопросов.")
        await start_fsm_scenario(message, state)
    else:
        await message.answer("Сейчас подберем для вас удобное время...")
        await booking_handlers.start_booking_scenario(message, state)


@router.message(Command("my_lessons"))
async def handle_my_lessons_command(message: types.Message, state: FSMContext):
    """Обрабатывает команду /my_lessons из меню - запускает проверку записей."""
    logging.info(f"Пользователь {message.from_user.id} вызвал команду /my_lessons.")
    await message.answer("Один момент, проверяю ваши записи...")
    await check_booking_handlers.start_check_booking_flow(
        message=message,
        state=state,
        user_id=message.from_user.id,
        username=message.from_user.username
    )


@router.message(Command("faq"))
async def handle_faq_command(message: types.Message):
    """Обрабатывает команду /faq из меню - показывает меню с вопросами."""
    logging.info(f"Пользователь {message.from_user.id} вызвал команду /faq.")
    await message.answer("Выберите интересующий вас вопрос:", reply_markup=get_faq_menu())


@router.message(Command("help"))
async def handle_help_command(message: types.Message):
    """Обрабатывает команду /help из меню - вызывает менеджера."""
    logging.info(f"Пользователь {message.from_user.id} вызвал команду /help.")
    await message.answer("Понимаю, сейчас позову менеджера.")
    await notify_admin_of_request(bot=message.bot, user=message.from_user, request_text="Клиент вызвал команду /help")
# =============================================================================
# БЛОК Клавиатуры для меню
# =============================================================================


async def show_greeting_screen(message: types.Message, user, state: FSMContext, is_edit: bool = False):
    """
    Единая функция для отображения приветственного экрана.
    Корректно обрабатывает новых и существующих пользователей.
    Может как отправлять новое сообщение, так и редактировать старое.
    """
    await state.clear()
    
    if user.onboarding_completed:
        logging.info(f"Отображаем главное меню для существующего пользователя {user.id}.")
        active_lessons = await get_all_active_lessons(user.id)
        parent_name = user.user_data.get('parent_name', 'уважаемый родитель')
        text = f"Здравствуйте, {parent_name}! Рад вас снова видеть. Чем могу помочь?"
        reply_markup = get_existing_user_menu(len(active_lessons))
    else:
        logging.info(f"Отображаем онбординг для нового пользователя {user.id}.")
        text = (
            "Здравствуйте! Я Ноубаг, ваш личный AI-менеджер в школе 'No Bugs'.\n\n"
            "Рад нашему знакомству! Чтобы я мог вам помочь, давайте пройдем короткое знакомство."
        )
        reply_markup = InlineKeyboardBuilder().button(text="🚀 Начать знакомство", callback_data="start_onboarding").as_markup()

    if is_edit:
        await message.edit_text(text, reply_markup=reply_markup)
    else:
        await message.answer(text, reply_markup=reply_markup)

# =============================================================================
# БЛОК  Главный обработчик
# =============================================================================

@router.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    """Обрабатывает команду /start и показывает соответствующее меню."""
    ## LOG ##
    logging.info(f"Пользователь {message.from_user.id} запустил /start.")
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    await show_greeting_screen(message, user, state)

# =============================================================================
# БЛОК  Обработчики кнопок (Callback-запросы)
# =============================================================================

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    logging.info(f"Пользователь {callback.from_user.id} нажал кнопку 'main_menu'.")
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    await show_greeting_screen(callback.message, user, state, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "start_onboarding")
async def cq_start_onboarding(callback: types.CallbackQuery, state: FSMContext):
    """Запускает FSM-сценарий онбординга по кнопке."""
    ## LOG ##
    logging.info(f"User {callback.from_user.id} pressed 'start_onboarding'. Starting FSM.")
    await callback.message.edit_text("Отлично! Приступаем...")
    await start_fsm_scenario(callback.message, state)

@router.callback_query(F.data == "start_booking")
async def cq_start_booking(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает кнопку записи: новых ведет на онбординг, старых — на бронирование."""
    ## LOG ##
    logging.info(f"User {callback.from_user.id} pressed 'start_booking'.")
    await callback.answer()
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    if not user.onboarding_completed:
        ## LOG ##
        logging.info(f"User {user.id} is new, starting FSM onboarding from booking button.")
        await callback.message.edit_text("Отлично, давайте познакомимся! Задам всего пару вопросов.")
        await start_fsm_scenario(callback.message, state)
    else:
        ## LOG ##
        logging.info(f"User {user.id} is existing, starting booking flow directly.")
        await callback.message.edit_text("Сейчас подберем для вас удобное время...")
        await booking_handlers.start_booking_flow(callback.message, state)

@router.callback_query(F.data == "check_booking")
async def cq_check_booking(callback: types.CallbackQuery, state: FSMContext):
    ## LOG ##
    logging.info(f"User {callback.from_user.id} pressed 'check_booking'.")
    await callback.message.edit_text("Один момент, проверяю ваши записи...")
    await check_booking_handlers.start_check_booking_flow(message=callback.message, 
        state=state, 
        user_id=callback.from_user.id,
        username=callback.from_user.username)
    
@router.callback_query(F.data == "reschedule_booking")
async def cq_reschedule_booking(callback: types.CallbackQuery, state: FSMContext):
    ## LOG ##
    logging.info(f"User {callback.from_user.id} pressed 'reschedule_booking'.")
    await reschedule_handlers.start_reschedule_flow(
        message=callback.message, 
        state=state, 
        user_id=callback.from_user.id,
        username=callback.from_user.username
    )
    await callback.answer()
    
@router.callback_query(F.data == "cancellation_request")
async def cq_cancellation_request(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку 'Отменить занятие'.
    Запускает тот же сценарий, что и текстовая команда.
    """
    logging.info(f"Пользователь {callback.from_user.id} нажал кнопку отмены 'cancellation_request'.")
    await state.clear()
    # Мы берем ID из callback.from_user, что гарантирует получение ID пользователя, а не бота.
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
    active_lessons = await get_all_active_lessons(user.id)

    if not active_lessons:
        await callback.message.edit_text("Я перепроверил, но у вас действительно нет активных уроков для отмены.")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    if len(active_lessons) == 1:
        lesson = active_lessons[0]
        lesson_time_str = format_date_russian(lesson.scheduled_at, 'short')
        
        builder.button(
            text="Да, отменить запись",
            callback_data=CancelCallbackFactory(action="confirm", lesson_id=lesson.id).pack()
        )
        builder.button(
            text="Нет, всё в силе",
            callback_data=CancelCallbackFactory(action="reject").pack()
        )
        builder.adjust(2)
        
        await callback.message.edit_text(
            f"У вас запланирован урок на {lesson_time_str}.\n\n"
            f"Вы уверены, что хотите отменить эту запись?",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.message.edit_text("У вас есть несколько активных записей. Какую из них вы хотите отменить?")
        for lesson in active_lessons:
            child_name = user.user_data.get('child_name', 'ребенка') if user.user_data else 'ребенка'
            lesson_time_str = format_date_russian(lesson.scheduled_at, 'short')
            builder.button(
                text=f"Урок для {child_name.capitalize()} на {lesson_time_str}",
                callback_data=CancelCallbackFactory(action="select", lesson_id=lesson.id).pack()
            )
        builder.button(text="Я передумал(а)", callback_data=CancelCallbackFactory(action="reject").pack())
        builder.adjust(1)
        await callback.message.edit_text("Выберите урок:", reply_markup=builder.as_markup())
    
    await callback.answer()

@router.callback_query(F.data == "human_operator")
async def cq_human_operator(callback: types.CallbackQuery):
    ## LOG ##
    logging.info(f"User {callback.from_user.id} pressed 'human_operator'. Notifying admin.")
    await callback.message.answer("Понимаю, сейчас позову менеджера.")
    await notify_admin_of_request(bot=callback.bot, user=callback.from_user, request_text="Клиент нажал кнопку 'Позвать менеджера'")
    await callback.answer()

@router.callback_query(F.data == "faq_menu")
async def cq_faq_menu(callback: types.CallbackQuery):
    ## LOG ##
    logging.info(f"User {callback.from_user.id} opened FAQ menu.")
    await callback.message.edit_text("Выберите интересующий вас вопрос:", reply_markup=get_faq_menu())

@router.callback_query(F.data.startswith("faq_"))
async def cq_faq_answer(callback: types.CallbackQuery):
    """
    Обрабатывает нажатия на кнопки FAQ с расширенным логированием для отладки.
    """
    # Шаг 1: Логируем исходные данные, которые мы получили от кнопки
    raw_callback_data = callback.data
    logging.debug(f"Получен callback от кнопки FAQ: '{raw_callback_data}'")

    # Шаг 2: Извлекаем ключ для поиска
    question_key = raw_callback_data.split("_", 1)[1]
    logging.debug(f"Извлечен ключ для поиска шаблона: '{question_key}'")

    # Шаг 3: Логируем сам процесс поиска
    logging.info(f"Начинаю поиск шаблона по ключу: '{question_key}'")
    key, template = find_template_by_keywords(question_key)
    try:
        if template:
            # Если шаблон найден, все работает как и раньше
            user = await get_or_create_user(callback.from_user.id, callback.from_user.username)
            response = await build_template_response(template, [], user.user_data)
            await callback.message.edit_text(response, reply_markup=get_faq_menu())
        else:
            # --- УЛУЧШЕННЫЙ БЛОК ОБРАБОТКИ ОШИБКИ ---
            logging.warning(f"ОШИБКА: Шаблон для FAQ-ключа '{question_key}' НЕ НАЙДЕН.")

            # 1. Теперь мы ДЕЙСТВИТЕЛЬНО вызываем менеджера
            await notify_admin_of_request(
                bot=callback.bot,
                user=callback.from_user,
                request_text=f"Пользователь нажал кнопку FAQ «{question_key}», но я не нашел ответ. Требуется помощь."
            )

            # 2. Отправляем пользователю честный и заботливый ответ
            await callback.message.edit_text(
                "Простите, я не смог найти точный ответ на этот вопрос в своей базе знаний. "
                "Но не волнуйтесь, я уже передал ваш запрос менеджеру, и он скоро с вами свяжется, чтобы помочь.",
                reply_markup=get_faq_menu()
            )
            
    except TelegramBadRequest as e:
        # 3. Ловим ошибку "message is not modified", чтобы избежать падения
        if "message is not modified" in e.message:
            logging.warning("Попытка отредактировать сообщение на идентичное. Игнорируем.")
        else:
            raise # Если ошибка другая, ее нужно видеть

    finally:
        # В любом случае "закрываем часики" на кнопке
        await callback.answer()


# =============================================================================
# БЛОК 4: Обработчик любых текстовых сообщений
# =============================================================================

@router.message(F.text, ~CommandStart())
async def handle_any_text(message: types.Message, state: FSMContext):
    """Главный диспетчер текстовых сообщений с полной логикой."""
    ## LOG ##
    logging.info(f"Обработка текстового сообщения от пользователя {message.from_user.id}. Текст: '{message.text}'")
    original_text = message.text.strip()
    corrected_text = correct_keyboard_layout(original_text)
    
    # Используем исправленный текст, если он был исправлен, иначе - оригинальный
    user_text = corrected_text if corrected_text else original_text
    logging.info(f"Обработка сообщения от {message.from_user.id}. Оригинал: '{original_text}', Исправлено: '{user_text}'")
    history = await load_history(str(message.from_user.id))
    try:
        user = await get_or_create_user(message.from_user.id, message.from_user.username)
        if user.is_blocked:
            ## LOG ##
            logging.warning(f"Заблокированный пользователь {user.id} пытался отправить сообщение.")
            await message.answer(
                "Ваш аккаунт был временно ограничен из-за превышения лимита запросов не по теме. \n\n"
                "Но не волнуйтесь, я уже передал всю информацию менеджеру, и он скоро с вами свяжется, чтобы во всем разобраться."
            )
            return
        # Проверяем, если пользователь еще не прошел онбординг,
        # то любое его текстовое сообщение будет запускать сценарий знакомства.
        if not user.onboarding_completed:
            logging.info(f"Новый пользователь {user.id} Отправили первое сообщение. Начинаем адаптацию")
            await show_greeting_screen(message, user, state)
            return
        await save_history(str(user.id), "user", message.text.strip())
        user_text = message.text.strip()
        
        detected_intent = intent_recognizer_service.get_intent(user_text.lower())
        
        # Если интент распознан, логируем и обрабатываем
        if detected_intent:
            ## LOG ##
            logging.info(f"Намерение распознано для пользователя {user.id}: '{detected_intent}'.")
            match detected_intent:
                case "booking_request":
                    await message.answer("Конечно! Нажмите кнопку ниже, чтобы начать.", 
                        reply_markup=InlineKeyboardBuilder().button(text="✍️ Записаться", 
                        callback_data="start_booking").as_markup())
                    return
                case "cancellation":
                    await start_cancellation_flow(
                        message=message, 
                        state=state, 
                        user_id=user.id, 
                        username=message.from_user.username
                    )
                    return
                case "reschedule":
                    await reschedule_handlers.start_reschedule_flow(
                        message=message, 
                        state=state, 
                        user_id=user.id, 
                        username=message.from_user.username
                    )
                    return
                case "check_booking":
                    await check_booking_handlers.start_check_booking_flow(
                        message=message,
                        state=state,
                        user_id=message.from_user.id,
                        username=message.from_user.username
                    )
                    return
                case "price_request" | "course_details" | "social_status_info" | "lesson_individuality":
                    template = TEMPLATES.get(detected_intent)
                    
                    if template:
                        # Если шаблон существует, строим и отправляем ответ
                        response = await build_template_response(template, history, user.user_data)
                        # Создаем клавиатуру по умолчанию (без кнопок)
                        keyboard = None
                        if detected_intent == "lesson_individuality":
                            builder = InlineKeyboardBuilder()
                            builder.button(text="✍️ Да, записаться на пробный урок", callback_data="start_booking")
                            keyboard = builder.as_markup()
                        await message.answer(response, reply_markup=keyboard)
                        return
                    else:
                        # Эта ветка сработает только в случае ошибки разработчика
                        # (интент есть, а шаблона для него нет)
                        logging.error(f"КРИТИЧЕСКАЯ ОШИБКА: Интент '{detected_intent}' есть, но шаблон для него в templates.py отсутствует!")
                case "greeting":
                    user = await get_or_create_user(message.from_user.id, message.from_user.username)
                    parent_name = user.user_data.get('parent_name', message.from_user.first_name)
                    await show_greeting_screen(message, user, state)
                    return
                case "human_operator":
                    await message.answer("Понимаю, сейчас позову менеджера."); await notify_admin_of_request(bot=message.bot, user=message.from_user, request_text=user_text); return

        ## LOG ##
        logging.info(f"No direct intent match for user {user.id}. Proceeding to relevancy check and LLM.")
        
        if not await is_query_relevant_ai(user_text, history):
            ## LOG ##
            logging.warning(f"Запрос от пользователя {user.id} отмечен как нерелевантный.")
            user.irrelevant_count += 1
            remaining_attempts = IRRELEVANT_QUERY_LIMIT - user.irrelevant_count
            if remaining_attempts > 0:
                await increment_irrelevant_count(user.id)
                await message.answer(
                    "Простите, не совсем вас понял. Похоже, в вашем сообщении опечатка или оно не связано с работой нашей школы. \n\n"
                    "Пожалуйста, попробуйте переформулировать ваш вопрос. Я здесь, чтобы помочь с курсами по программированию."
                )
            else:
                ## LOG ##
                logging.warning(f"Блокировка пользователя {user.id} из-за повторяющихся нерелевантных запросов")
                await block_user(user.id)
                await notify_admin_of_block(
                    bot=message.bot, 
                    user=message.from_user, 
                    history=history,
                    reason="Превышен лимит нерелевантных запросов" # Добавляем причину
                )
                await message.answer("Вы исчерпали лимит запросов не по теме. Чтобы продолжить, обратитесь к менеджеру, я ему уже всё передал.")
            return

        ## LOG ##
        logging.info(f"Query from {user.id} is relevant. Sending to LLM.")
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        llm_response = await get_llm_response(user_text, history)
        await message.answer(llm_response)

    except Exception as e:
        ## LOG ##
        logging.error(f"CRITICAL ERROR in 'handle_any_text' from {message.from_user.id}: {e}", exc_info=True)
        await notify_admin_on_error(bot=message.bot, user_id=message.from_user.id, username=message.from_user.username, error_description=str(e), history=history)
        await message.answer("Ой, произошла ошибка. Я уже сообщил команде. Попробуйте, пожалуйста, позже.")
