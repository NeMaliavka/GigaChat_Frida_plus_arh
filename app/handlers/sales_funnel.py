import logging
from aiogram import Router, types, F

from app.core.template_service import find_template, choose_variant
from app.core.llm_service import get_llm_response
from app.db.database import save_history, load_history
# НОВИНКА: Импортируем vectorstore напрямую для проверки релевантности
from app.knowledge_base.loader import vectorstore

router = Router()

# НОВИНКА: Жестко запрограммированный ответ на все нерелевантные вопросы
OFFTOPIC_RESPONSE = "Это интересный вопрос, но он выходит за рамки моей компетенции как ассистента школы программирования. Давайте лучше вернемся к обсуждению наших курсов. Возможно, вас интересуют подробности о преподавателях?"

@router.message(F.text)
async def handle_any_text(message: types.Message):
    """
    Основной обработчик с финальной логикой "фейс-контроля":
    1. Поиск по шаблонам.
    2. Если шаблон не найден — проверка релевантности по базе знаний.
    3. Если нерелевантно — отправка жесткого ответа-отказа БЕЗ ОБРАЩЕНИЯ К AI.
    4. Только если релевантно — обращение к LLM.
    """
    user_id = str(message.from_user.id)
    user_text = message.text

    await save_history(user_id, "user", user_text)
    history = await load_history(user_id)
    
    # Шаг 1: Попытка найти быстрый ответ в шаблонах
    _template_key, template_value = find_template(user_text)
    
    if template_value:
        response_text = choose_variant(template_value, history)
        logging.info(f"Ответ найден в шаблонах для запроса: '{user_text}'")
    else:
        # Шаг 2: Шаблон не найден. Проверка на релевантность (фейс-контроль)
        logging.info("Шаблон не найден. Проверка релевантности запроса...")
        DISTANCE_THRESHOLD = 0.9 # Немного ослабим порог, чтобы не отсекать близкие по теме вопросы
        docs_with_scores = vectorstore.similarity_search_with_score(user_text, k=1)
        
        # Проверка, что найден хотя бы один документ и его оценка ниже порога
        is_relevant = docs_with_scores and docs_with_scores[0][1] < DISTANCE_THRESHOLD

        if is_relevant:
            # Шаг 3: Если проверка пройдена — обращаемся к LLM
            logging.info(f"Запрос признан релевантным (оценка: {docs_with_scores[0][1]}). Обращение к GigaChat.")
            response_text = get_llm_response(question=user_text, history=history)
        else:
            # Шаг 4: Если проверка НЕ пройдена — отправляем заготовку
            logging.warning(f"Запрос '{user_text}' признан нерелевантным. Отправка стандартного ответа.")
            response_text = OFFTOPIC_RESPONSE
            
    await message.answer(response_text)
    await save_history(user_id, "assistant", response_text)
