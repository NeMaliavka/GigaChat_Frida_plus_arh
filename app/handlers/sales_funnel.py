# # import logging
# # import json
# # import re
# # from pathlib import Path
# # from html import escape

# # from aiogram import Router, types, F
# # from aiogram.fsm.context import FSMContext
# # from aiogram.fsm.state import State, StatesGroup
# # from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# # # Импортируем все необходимые сервисы и функции
# # from app.core.template_service import find_template_by_keywords, build_template_response
# # from app.core.llm_service import get_llm_response, is_query_relevant_ai, correct_user_query
# # from app.core.business_logic import process_final_data
# # from app.core.admin_notifications import notify_admin_on_error, notify_admin_on_suspicious_activity
# # from app.db.database import get_or_create_user, save_user_details, save_history, load_history, set_onboarding_completed
# # from app.keyboards.inline import get_enroll_keyboard

# # # Импортируем утилиты, обрабатывая возможное их отсутствие
# # try:
# #     from app.utils.text_tools import correct_keyboard_layout, is_plausible_name, inflect_name
# #     MORPHOLOGY_ENABLED = True
# # except ImportError:
# #     logging.warning("Утилиты (text_tools.py) не найдены. Расширенные функции будут отключены.")
# #     MORPHOLOGY_ENABLED = False
# #     def correct_keyboard_layout(_: str) -> None: return None
# #     def is_plausible_name(_: str) -> bool: return True
# #     def inflect_name(name: str, _: str) -> str: return name

# # router = Router()

# # # --- Загрузка FSM-сценария ---
# # FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"
# # try:
# #     with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
# #         FSM_CONFIG = json.load(f)
# # except (FileNotFoundError, json.JSONDecodeError) as e:
# #     logging.error(f"Критическая ошибка: не удалось загрузить FSM-сценарий. {e}")
# #     FSM_CONFIG = {}

# # # --- FSM-модели ---
# # class GenericFSM(StatesGroup):
# #     InProgress = State()

# # class WaitlistFSM(StatesGroup):
# #     waiting_for_contact = State()

# # def _format_response_with_inflection(template: str, data: dict) -> str:
# #     """Форматирует строку, склоняя имена в нужный падеж."""
# #     if not MORPHOLOGY_ENABLED or not template:
# #         return template.format(**data) if template else ""
# #     def repl(match):
# #         var_name, case = match.groups()
# #         return inflect_name(data.get(var_name, ""), case)
# #     processed_template = re.sub(r'\{(\w+):(\w+)\}', repl, template)
# #     final_data = {k: (v.capitalize() if isinstance(v, str) else v) for k, v in data.items()}
# #     return processed_template.format(**final_data)

# # # --- Обработчики для записи в лист ожидания ---
# # @router.callback_query(F.data == "waitlist:join")
# # async def handle_waitlist_join(callback: types.CallbackQuery, state: FSMContext):
# #     await callback.message.edit_text("Отлично! Пожалуйста, оставьте ваш номер телефона или email, и мы сообщим о запуске.")
# #     await state.set_state(WaitlistFSM.waiting_for_contact)
# #     await callback.answer()

# # @router.callback_query(F.data == "waitlist:cancel")
# # async def handle_waitlist_cancel(callback: types.CallbackQuery, state: FSMContext):
# #     await callback.message.edit_text("Хорошо, мы вас поняли. Если передумаете, мы всегда на связи!")
# #     await callback.answer()

# # @router.message(WaitlistFSM.waiting_for_contact)
# # async def process_waitlist_contact(message: types.Message, state: FSMContext):
# #     contact_info = message.text
# #     user = await get_or_create_user(message.from_user.id, message.from_user.username)
# #     current_data = user.user_data or {}
# #     current_data['waitlist_contact'] = contact_info
# #     current_data['waitlist_for_age'] = '<9'
# #     await save_user_details(telegram_id=user.telegram_id, data=current_data)
# #     logging.info(f"Пользователь {user.telegram_id} добавлен в лист ожидания: {contact_info}")
# #     await message.answer("Спасибо! Мы сохранили ваши данные и обязательно с вами свяжемся.")
# #     await state.clear()


# # # --- Логика основного FSM-сценария ---
# # async def start_fsm_scenario(message: types.Message, state: FSMContext):
# #     if not FSM_CONFIG:
# #         await message.answer("Извините, функция записи временно недоступна.")
# #         return
# #     initial_step_name = FSM_CONFIG.get("initial_state")
# #     initial_step_config = FSM_CONFIG.get("states", {}).get(initial_step_name)
# #     if not initial_step_config:
# #         logging.error("Критическая ошибка: не найден initial_state в fsm_scenario.json")
# #         await message.answer("Ой, у меня небольшая техническая заминка.")
# #         return
# #     logging.info(f"Запускаем сценарий '{FSM_CONFIG.get('scenario_name', 'N/A')}' для {message.from_user.id}")
# #     await state.set_state(GenericFSM.InProgress)
# #     await state.set_data({'current_step': initial_step_name})
# #     intro_text = FSM_CONFIG.get("onboarding_intro", "")
# #     first_question = initial_step_config.get("question", "Как я могу к вам обращаться?")
# #     await message.answer(intro_text + first_question)

# # async def _advance_fsm_step(message: types.Message, state: FSMContext, fsm_data: dict):
# #     current_step_name = fsm_data.get("current_step")
# #     current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name, {})
# #     next_step_name = current_step_config.get("next_state")
# #     if next_step_name:
# #         next_step_config = FSM_CONFIG.get("states", {}).get(next_step_name)
# #         if not next_step_config:
# #             return
# #         fsm_data['current_step'] = next_step_name
# #         await state.set_data(fsm_data)
# #         next_question = _format_response_with_inflection(next_step_config.get("question"), fsm_data)
# #         await message.answer(next_question)
# #     else:
# #         # Финал сценария
# #         await set_onboarding_completed(message.from_user.id)
# #         processed_data = process_final_data(fsm_data)
# #         final_template = FSM_CONFIG.get("final_message_template", "Спасибо!")
# #         final_text = _format_response_with_inflection(final_template, processed_data)
# #         await message.answer(final_text, reply_markup=get_enroll_keyboard())
# #         await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
# #         await state.clear()

# # @router.callback_query(F.data.startswith("confirm_layout:"))
# # async def process_layout_confirmation(callback: types.CallbackQuery, state: FSMContext):
# #     fsm_data = await state.get_data()
# #     action = callback.data.split(":")[1]
# #     final_input = fsm_data.get("suggested_input") if action == "yes" else fsm_data.get("original_input")
# #     await callback.message.edit_text(f"Отлично! Записал: {final_input.capitalize()}.")
# #     target_key = fsm_data.pop("target_data_key")
# #     fsm_data[target_key] = final_input
# #     await state.set_data(fsm_data)
# #     fsm_data.pop("original_input", None)
# #     fsm_data.pop("suggested_input", None)
# #     await _advance_fsm_step(callback.message, state, fsm_data)
# #     await callback.answer()

# # @router.message(GenericFSM.InProgress)
# # async def handle_fsm_step(message: types.Message, state: FSMContext):
# #     user_text = message.text.strip()
# #     fsm_data = await state.get_data()
# #     current_step_name = fsm_data.get("current_step")
# #     current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name)

# #     if not current_step_config:
# #         error_text = f"Ошибка в конфигурации сценария. Не найден шаг: {current_step_name}"
# #         history = await load_history(str(message.from_user.id), limit=10)
# #         await notify_admin_on_error(bot=message.bot, user_id=message.from_user.id, username=message.from_user.username, error_description=error_text, history=history)
# #         await message.answer("Ой, у меня техническая заминка. Уже позвал администратора, он скоро подключится!")
# #         await state.clear()
# #         return

# #     # Коррекция раскладки
# #     if MORPHOLOGY_ENABLED and current_step_config.get("needs_layout_correction", False):
# #         if corrected_text := correct_keyboard_layout(user_text):
# #             await state.update_data(original_input=user_text, suggested_input=corrected_text, target_data_key=current_step_config["data_key"])
# #             keyboard = InlineKeyboardMarkup(inline_keyboard=[
# #                 [InlineKeyboardButton(text=f"Да, это «{corrected_text.capitalize()}»", callback_data="confirm_layout:yes")],
# #                 [InlineKeyboardButton(text="Нет, оставить как есть", callback_data="confirm_layout:no")]
# #             ])
# #             await message.answer(f"Вы ввели «{escape(user_text)}». Возможно, вы имели в виду «{corrected_text.capitalize()}»?", reply_markup=keyboard)
# #             return

# #     # Валидация
# #     validation_type = current_step_config.get("validation")
# #     is_valid = True
# #     if MORPHOLOGY_ENABLED and validation_type:
# #         if validation_type == "name": is_valid = is_plausible_name(user_text)
# #         elif validation_type == "digits": is_valid = user_text.isdigit()
    
# #     if not is_valid:
# #         await message.answer(current_step_config.get("error_message", "Неверный формат."))
# #         return
    
# #     data_key = current_step_config["data_key"]
# #     value_to_store = int(user_text) if validation_type == "digits" else user_text
# #     fsm_data[data_key] = value_to_store

# #     # ГАРАНТИРОВАННАЯ ПРОВЕРКА ВОЗРАСТА
# #     if data_key == 'child_age':
# #         age = value_to_store
# #         # Жесткая проверка возраста здесь, НЕЗАВИСИМО от business_logic
# #         if age < 9:
# #             response_text = ("На данный момент наши курсы рассчитаны на детей от 9 лет, но мы уже активно создаем программу для самых юных программистов!\n\nХотите, мы сообщим вам о запуске в числе первых? Это бесплатно и ни к чему не обязывает.")
# #             buttons = [InlineKeyboardButton(text="Да, сообщите мне!", callback_data="waitlist:join"), InlineKeyboardButton(text="Нет, спасибо", callback_data="waitlist:cancel")]
# #             reply_markup = InlineKeyboardMarkup(inline_keyboard=[buttons])
# #             await message.answer(response_text, reply_markup=reply_markup)
# #             await set_onboarding_completed(message.from_user.id)
# #             await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
# #             await state.clear()
# #             return
# #         elif age > 17:
# #             response_text = ("Здорово! В таком возрасте мы бы уже рекомендовали взрослые курсы для достижения максимального результата. У нас таких, к сожалению, нет, но мы уверены, что вы найдете отличный вариант!")
# #             await message.answer(response_text)
# #             await set_onboarding_completed(message.from_user.id)
# #             await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
# #             await state.clear()
# #             return

# #     # Если возраст подошел, продолжаем сценарий
# #     await _advance_fsm_step(message, state, fsm_data)


# # # --- Единый обработчик для всех текстовых сообщений ---
# # @router.message(F.text)
# # async def handle_any_text(message: types.Message, state: FSMContext):
# #     user_id_str = str(message.from_user.id)
# #     user_text = message.text.strip()
# #     user = await get_or_create_user(message.from_user.id, message.from_user.username)
# #     await save_history(user_id_str, "user", user_text)
    
# #     if not user.onboarding_completed:
# #         await start_fsm_scenario(message, state)
# #         return

# #     # Логика "Фриды" для ответов на вопросы
# #     history = await load_history(user_id_str)
# #     response_text = ""
# #     user_data = user.user_data or {}
# #     child_age_str = str(user_data.get("child_age", "0"))
# #     child_age = int(child_age_str) if child_age_str.isdigit() else 0
# #     context_key = "course_junior" if 9 <= child_age <= 13 else ("course_senior" if 14 <= child_age <= 17 else "default")
    
# #     _template_key, template_data = find_template_by_keywords(user_text)
    
# #     if template_data:
# #         await state.update_data(offtopic_count=0)
# #         # Передаем найденный шаблон и историю для сборки "умного" ответа
# #         response_text = build_template_response(template_data, history)
# #     else:
# #         corrected_text = await correct_user_query(user_text)
# #         if await is_query_relevant_ai(corrected_text, history):
# #             await state.update_data(offtopic_count=0)
# #             response_text = await get_llm_response(question=corrected_text, history=history, context_key=context_key)
# #         else:
# #             data = await state.get_data()
# #             offtopic_count = data.get("offtopic_count", 0) + 1
# #             await state.update_data(offtopic_count=offtopic_count)
# #             if offtopic_count >= 3:
# #                 await notify_admin_on_suspicious_activity(
# #                     bot=message.bot, user_id=message.from_user.id, username=message.from_user.username, history=history
# #                 )
# #                 await message.answer("Я вижу, что вас интересуют вопросы, не связанные с нашей школой. Вынужден приостановить диалог.")
# #             else:
# #                 await message.answer(f"Это интересный вопрос, но он не относится к работе нашей школы. (Осталось попыток: {3 - offtopic_count})")
    
# #     if response_text:
# #         await message.answer(response_text)
# #         await save_history(user_id_str, "assistant", response_text)

# import logging
# import json
# import re
# from pathlib import Path
# from html import escape

# from aiogram import Router, types, F
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
# # ИСПРАВЛЕНО: Добавляем фильтр для исключения команд
# from aiogram.filters import CommandStart

# # Импортируем все необходимые сервисы и функции
# from app.core.template_service import find_template_by_keywords, build_template_response
# from app.core.llm_service import get_llm_response, is_query_relevant_ai, correct_user_query
# from app.core.business_logic import process_final_data
# from app.core.admin_notifications import notify_admin_on_error, notify_admin_on_suspicious_activity
# from app.db.database import get_or_create_user, save_user_details, save_history, load_history, set_onboarding_completed
# from app.keyboards.inline import get_enroll_keyboard

# # Импортируем утилиты
# try:
#     from app.utils.text_tools import correct_keyboard_layout, is_plausible_name, inflect_name
#     MORPHOLOGY_ENABLED = True
# except ImportError:
#     logging.warning("Утилиты (text_tools.py) не найдены. Расширенные функции будут отключены.")
#     MORPHOLOGY_ENABLED = False
#     def correct_keyboard_layout(_: str) -> None: return None
#     def is_plausible_name(_: str) -> bool: return True
#     def inflect_name(name: str, _: str) -> str: return name

# router = Router()

# # --- Загрузка FSM-сценария ---
# FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"
# try:
#     with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
#         FSM_CONFIG = json.load(f)
# except (FileNotFoundError, json.JSONDecodeError) as e:
#     logging.error(f"Критическая ошибка: не удалось загрузить FSM-сценарий. {e}")
#     FSM_CONFIG = {}

# # --- FSM-модели ---
# class GenericFSM(StatesGroup):
#     InProgress = State()

# class WaitlistFSM(StatesGroup):
#     waiting_for_contact = State()

# def _format_response_with_inflection(template: str, data: dict) -> str:
#     if not MORPHOLOGY_ENABLED or not template:
#         return template.format(**data) if template else ""
#     def repl(match):
#         var_name, case = match.groups()
#         return inflect_name(data.get(var_name, ""), case)
#     processed_template = re.sub(r'\{(\w+):(\w+)\}', repl, template)
#     final_data = {k: " ".join(w.capitalize() for w in v.split()) if isinstance(v, str) else v for k, v in data.items()}
#     return processed_template.format(**final_data)

# # --- Обработчики для листа ожидания ---
# @router.callback_query(F.data == "waitlist:join")
# async def handle_waitlist_join(callback: types.CallbackQuery, state: FSMContext):
#     await callback.message.edit_text("Отлично! Пожалуйста, оставьте ваш номер телефона или email, и мы сообщим о запуске.")
#     await state.set_state(WaitlistFSM.waiting_for_contact)
#     await callback.answer()

# @router.callback_query(F.data == "waitlist:cancel")
# async def handle_waitlist_cancel(callback: types.CallbackQuery, state: FSMContext):
#     await callback.message.edit_text("Хорошо, мы вас поняли. Если передумаете, мы всегда на связи!")
#     await callback.answer()

# @router.message(WaitlistFSM.waiting_for_contact)
# async def process_waitlist_contact(message: types.Message, state: FSMContext):
#     contact_info = message.text
#     user = await get_or_create_user(message.from_user.id, message.from_user.username)
#     current_data = user.user_data or {}
#     current_data['waitlist_contact'] = contact_info
#     current_data['waitlist_for_age'] = '<9'
#     await save_user_details(telegram_id=user.telegram_id, data=current_data)
#     logging.info(f"Пользователь {user.telegram_id} добавлен в лист ожидания: {contact_info}")
#     await message.answer("Спасибо! Мы сохранили ваши данные и обязательно с вами свяжемся.")
#     await state.clear()


# # --- Логика основного FSM-сценария ---
# async def start_fsm_scenario(message: types.Message, state: FSMContext):
#     if not FSM_CONFIG:
#         await message.answer("Извините, функция записи временно недоступна.")
#         return
#     initial_step_name = FSM_CONFIG.get("initial_state")
#     initial_step_config = FSM_CONFIG.get("states", {}).get(initial_step_name)
#     if not initial_step_config:
#         return
#     logging.info(f"Запускаем сценарий '{FSM_CONFIG.get('scenario_name', 'N/A')}' для {message.from_user.id}")
#     await state.set_state(GenericFSM.InProgress)
#     await state.set_data({'current_step': initial_step_name})
#     intro_text = FSM_CONFIG.get("onboarding_intro", "")
#     first_question = initial_step_config.get("question", "Как я могу к вам обращаться?")
#     await message.answer(intro_text + first_question)

# async def _advance_fsm_step(message: types.Message, state: FSMContext, fsm_data: dict):
#     current_step_name = fsm_data.get("current_step")
#     current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name, {})
#     next_step_name = current_step_config.get("next_state")
#     if next_step_name:
#         next_step_config = FSM_CONFIG.get("states", {}).get(next_step_name)
#         if not next_step_config:
#             return
#         fsm_data['current_step'] = next_step_name
#         await state.set_data(fsm_data)
#         next_question = _format_response_with_inflection(next_step_config.get("question"), fsm_data)
#         await message.answer(next_question)
#     else:
#         await set_onboarding_completed(message.from_user.id)
#         processed_data = process_final_data(fsm_data)
#         final_template = FSM_CONFIG.get("final_message_template", "Спасибо!")
#         final_text = _format_response_with_inflection(final_template, processed_data)
#         await message.answer(final_text, reply_markup=get_enroll_keyboard())
#         await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
#         await state.clear()

# @router.callback_query(F.data.startswith("confirm_layout:"))
# async def process_layout_confirmation(callback: types.CallbackQuery, state: FSMContext):
#     fsm_data = await state.get_data()
#     action = callback.data.split(":")[1]
#     final_input = fsm_data.get("suggested_input") if action == "yes" else fsm_data.get("original_input")
#     await callback.message.edit_text(f"Отлично! Записал: {final_input.capitalize()}.")
#     target_key = fsm_data.pop("target_data_key")
#     fsm_data[target_key] = final_input
#     await state.set_data(fsm_data)
#     fsm_data.pop("original_input", None)
#     fsm_data.pop("suggested_input", None)
#     await _advance_fsm_step(callback.message, state, fsm_data)
#     await callback.answer()

# @router.message(GenericFSM.InProgress)
# async def handle_fsm_step(message: types.Message, state: FSMContext):
#     user_text = message.text.strip()
#     fsm_data = await state.get_data()
#     current_step_name = fsm_data.get("current_step")
#     current_step_config = FSM_CONFIG.get("states", {}).get(current_step_name)

#     if not current_step_config:
#         return
        
#     if MORPHOLOGY_ENABLED and current_step_config.get("needs_layout_correction", False):
#         if corrected_text := correct_keyboard_layout(user_text):
#             await state.update_data(original_input=user_text, suggested_input=corrected_text, target_data_key=current_step_config["data_key"])
#             keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Да, это «{corrected_text.capitalize()}»", callback_data="confirm_layout:yes")], [InlineKeyboardButton(text="Нет, оставить как есть", callback_data="confirm_layout:no")]])
#             await message.answer(f"Вы ввели «{escape(user_text)}». Возможно, вы имели в виду «{corrected_text.capitalize()}»?", reply_markup=keyboard)
#             return

#     validation_type = current_step_config.get("validation")
#     is_valid = True
#     if MORPHOLOGY_ENABLED and validation_type:
#         if validation_type == "name": is_valid = is_plausible_name(user_text)
#         elif validation_type == "digits": is_valid = user_text.isdigit()
    
#     if not is_valid:
#         await message.answer(current_step_config.get("error_message", "Неверный формат."))
#         return
    
#     data_key = current_step_config["data_key"]
#     value_to_store = int(user_text) if validation_type == "digits" else user_text
#     fsm_data[data_key] = value_to_store

#     if data_key == 'child_age':
#         age = value_to_store
#         if age < 9 or age > 17:
#             response_text = "На данный момент наши курсы рассчитаны на детей от 9 лет, но мы уже активно создаем программу для самых юных программистов!\n\nХотите, мы сообщим вам о запуске в числе первых?" if age < 9 else "Здорово! В таком возрасте мы бы уже рекомендовали взрослые курсы для достижения максимального результата."
#             buttons = [InlineKeyboardButton(text="Да, сообщите мне!", callback_data="waitlist:join"), InlineKeyboardButton(text="Нет, спасибо", callback_data="waitlist:cancel")] if age < 9 else []
#             reply_markup = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
#             await message.answer(response_text, reply_markup=reply_markup)
#             await set_onboarding_completed(message.from_user.id)
#             await save_user_details(telegram_id=message.from_user.id, data=fsm_data)
#             await state.clear()
#             return

#     await _advance_fsm_step(message, state, fsm_data)

# # ИСПРАВЛЕНО: Добавляем фильтр ~CommandStart(), чтобы этот хендлер не срабатывал на команду /start
# @router.message(F.text, ~CommandStart())
# async def handle_any_text(message: types.Message, state: FSMContext):
#     user_id_str = str(message.from_user.id)
#     user_text = message.text.strip()
#     user = await get_or_create_user(message.from_user.id, message.from_user.username)
#     await save_history(user_id_str, "user", user_text)
    
#     if not user.onboarding_completed:
#         await start_fsm_scenario(message, state)
#         return

#     # Логика "Фриды" для ответов на вопросы
#     history = await load_history(user_id_str)
#     response_text = ""
#     user_data = user.user_data or {}
#     child_age_str = str(user_data.get("child_age", "0"))
#     child_age = int(child_age_str) if child_age_str.isdigit() else 0
#     context_key = "course_junior" if 9 <= child_age <= 13 else ("course_senior" if 14 <= child_age <= 17 else "default")
    
#     _template_key, template_data = find_template_by_keywords(user_text)
    
#     if template_data:
#         await state.update_data(offtopic_count=0)
#         # Передаем найденный шаблон и историю для сборки "умного" ответа
#         response_text = build_template_response(template_data, history)
#     else:
#         corrected_text = await correct_user_query(user_text)
#         if await is_query_relevant_ai(corrected_text, history):
#             await state.update_data(offtopic_count=0)
#             response_text = await get_llm_response(question=corrected_text, history=history, context_key=context_key)
#         else:
#             data = await state.get_data()
#             offtopic_count = data.get("offtopic_count", 0) + 1
#             await state.update_data(offtopic_count=offtopic_count)
#             if offtopic_count >= 3:
#                 await notify_admin_on_suspicious_activity(
#                     bot=message.bot, user_id=message.from_user.id, username=message.from_user.username, history=history
#                 )
#                 await message.answer("Я вижу, что вас интересуют вопросы, не связанные с нашей школой. Вынужден приостановить диалог.")
#             else:
#                 await message.answer(f"Это интересный вопрос, но он не относится к работе нашей школы. (Осталось попыток: {3 - offtopic_count})")
    
#     if response_text:
#         await message.answer(response_text)
#         await save_history(user_id_str, "assistant", response_text)

import logging
import json
import re
from pathlib import Path
from html import escape
from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
# Фильтр для исключения команд из текстового обработчика
from aiogram.filters import CommandStart

# Импортируем все необходимые сервисы и функции
from app.core.template_service import find_template_by_keywords, build_template_response
from app.core.llm_service import get_llm_response, is_query_relevant_ai, correct_user_query
from app.core.business_logic import process_final_data
from app.core.admin_notifications import notify_admin_on_error, notify_admin_on_suspicious_activity
# Убедитесь, что имена функций соответствуют вашему файлу database.py
from app.db.database import get_or_create_user, save_user_details, save_history, load_history, set_onboarding_completed, get_last_message_time
from app.keyboards.inline import get_enroll_keyboard

# Импортируем утилиты, обрабатывая возможное их отсутствие
try:
    from app.utils.text_tools import correct_keyboard_layout, is_plausible_name, inflect_name
    MORPHOLOGY_ENABLED = True
except ImportError:
    logging.warning("Утилиты (text_tools.py) не найдены. Расширенные функции (коррекция, валидация, склонение) будут отключены.")
    MORPHOLOGY_ENABLED = False
    # Создаем "заглушки", чтобы код не падал
    def correct_keyboard_layout(_: str) -> None: return None
    def is_plausible_name(_: str) -> bool: return True
    def inflect_name(name: str, _: str) -> str: return name

router = Router()

# --- Загрузка FSM-сценария ---
FSM_SCENARIO_PATH = Path(__file__).parent.parent / "knowledge_base" / "scenarios" / "fsm_scenario.json"
try:
    with open(FSM_SCENARIO_PATH, 'r', encoding='utf-8') as f:
        FSM_CONFIG = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"Критическая ошибка: не удалось загрузить FSM-сценарий. {e}")
    FSM_CONFIG = {}

# --- FSM-модели ---
class GenericFSM(StatesGroup):
    InProgress = State()

class WaitlistFSM(StatesGroup):
    waiting_for_contact = State()

def _format_response_with_inflection(template: str, data: dict) -> str:
    """Форматирует строку, склоняя имена и корректно капитализируя их."""
    if not MORPHOLOGY_ENABLED or not template:
        return template.format(**data) if template else ""
    
    # Сначала обрабатываем склоняемые плейсхолдеры
    def repl(match):
        var_name, case = match.groups()
        return inflect_name(data.get(var_name, ""), case)
    
    processed_template = re.sub(r'\{(\w+):(\w+)\}', repl, template)

    # Затем готовим данные для остальных плейсхолдеров, капитализируя каждое слово
    final_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            final_data[key] = " ".join(word.capitalize() for word in value.split())
        else:
            final_data[key] = value
            
    return processed_template.format(**final_data)

# --- Обработчики для записи в лист ожидания ---
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


# --- Логика основного FSM-сценария ---
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
            return
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
        await message.answer(final_text, reply_markup=get_enroll_keyboard())
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
    fsm_data.pop("original_input", None)
    fsm_data.pop("suggested_input", None)
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

    # Коррекция раскладки
    if MORPHOLOGY_ENABLED and current_step_config.get("needs_layout_correction", False):
        if corrected_text := correct_keyboard_layout(user_text):
            await state.update_data(original_input=user_text, suggested_input=corrected_text, target_data_key=current_step_config["data_key"])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Да, это «{corrected_text.capitalize()}»", callback_data="confirm_layout:yes")], [InlineKeyboardButton(text="Нет, оставить как есть", callback_data="confirm_layout:no")]])
            await message.answer(f"Вы ввели «{escape(user_text)}». Возможно, вы имели в виду «{corrected_text.capitalize()}»?", reply_markup=keyboard)
            return

    # Валидация
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

    # ГАРАНТИРОВАННАЯ ПРОВЕРКА ВОЗРАСТА
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

    # Если возраст подошел, продолжаем сценарий
    await _advance_fsm_step(message, state, fsm_data)


# --- Единый обработчик для всех текстовых сообщений ---
# Он не будет срабатывать на команду /start, так как она обрабатывается в common.py
@router.message(F.text, ~CommandStart())
async def handle_any_text(message: types.Message, state: FSMContext):
    user_id_str = str(message.from_user.id)
    user_text = message.text.strip()
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    await save_history(user_id_str, "user", user_text)
    
    if not user.onboarding_completed:
        await start_fsm_scenario(message, state)
        return

    # --- ПРИВЕТСТВИЕ ПО ВРЕМЕНИ НЕАКТИВНОСТИ ---
    last_msg_time = await get_last_message_time(user.id)
    if last_msg_time and (datetime.now() - last_msg_time > timedelta(hours=7)):
        parent_name = (user.user_data or {}).get('parent_name', 'Гость')
        capitalized_name = " ".join(word.capitalize() for word in parent_name.split())
        await message.answer(f"С возвращением, {capitalized_name}! Рад вас снова видеть.\nЧем могу помочь сегодня?")
        # Не прерываем выполнение, чтобы текущий запрос тоже был обработан

    # Логика "Фриды" для ответов на вопросы
    history = await load_history(user_id_str)
    
    # Сначала ищем ответ в шаблонах
    template_key, template_data = await find_template_by_keywords(user_text)
    if template_data:
        response_text = await build_template_response(template_data, history, user.user_data or {})
    else:
        # Если шаблон не найден, обращаемся к LLM
        corrected_text = await correct_user_query(user_text)
        if await is_query_relevant_ai(corrected_text, history):
            response_text = await get_llm_response(question=corrected_text, history=history, context_key="default")
        else:
            # Обработка нерелевантного запроса
            data = await state.get_data()
            offtopic_count = data.get("offtopic_count", 0) + 1
            await state.update_data(offtopic_count=offtopic_count)
            if offtopic_count >= 3:
                await notify_admin_on_suspicious_activity(bot=message.bot, user_id=user.id, username=user.username, history=history)
                response_text = "Я вижу, что вас интересуют вопросы, не связанные с нашей школой. Вынужден приостановить диалог."
            else:
                response_text = f"Это интересный вопрос, но он не относится к работе нашей школы. (Осталось попыток: {3 - offtopic_count})"
    
    if response_text:
        await message.answer(response_text)
        await save_history(user_id_str, "assistant", response_text)

