import logging
from typing import List, Dict

from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage

from app.config import (
    SBERCLOUD_API_KEY, GIGACHAT_MODEL, GIGACHAT_MAX_TOKENS,
    KEYWORDS_PATH, DISTANCE_THRESHOLD
)
from app.knowledge_base.loader import vectorstore, SYSTEM_PROMPT


CLASSIFIER_PROMPT = """
Отвечай ТОЛЬКО "да" или "нет".
Твоя задача - определить, относится ли запрос пользователя к деятельности онлайн-школы программирования.

ЗАПРОСЫ, НА КОТОРЫЕ ОТВЕТ "ДА":
- Любые вопросы о курсах, ценах, расписании, пробных уроках.
- Прямые команды: "Записаться на урок", "Отменить запись", "Перенести встречу".
- Просьба позвать человека или менеджера.
- Нечеткие запросы, которые могут подразумевать интерес: "хочу попробовать", "как у вас тут".

ЗАПРОСЫ, НА КОТОРЫЕ ОТВЕТ "НЕТ":
- Случайный набор букв, бессмыслица.
- Вопросы на отвлеченные темы: "какая погода", "расскажи анекдот", "кто ты".
- Оскорбления или грубость.

ПРИМЕРЫ:
Пользователь: "Отменить запись"
Твой ответ: да
---
Пользователь: "ghbdtn"
Твой ответ: нет
---
Пользователь: "Хочу перенести пробный урок"
Твой ответ: да
"""

try:
    gigachat = GigaChat(
        credentials=SBERCLOUD_API_KEY,
        scope="GIGACHAT_API_PERS",
        model=GIGACHAT_MODEL,
        max_tokens=GIGACHAT_MAX_TOKENS,
        verify_ssl_certs=False,
    )
    logging.info(f"Основная модель GigaChat '{GIGACHAT_MODEL}' успешно инициализирована.")
except Exception as e:
    logging.error(f"Ошибка инициализации GigaChat: {e}", exc_info=True)
    gigachat = None


# --- AI-КОРРЕКТОР ---
async def correct_user_query(question: str) -> str:
    if not gigachat:
        return question

    corrector_prompt = (
        "Ты — редактор-корректор. Исправь орфографические и грамматические ошибки в предложении, "
        "полностью сохранив его первоначальный смысл и стиль. Если ошибок нет, верни исходное предложение без изменений.\n"
        f"Предложение: '{question}'"
    )
    try:
        response = await gigachat.ainvoke([SystemMessage(content=corrector_prompt)], max_tokens=150)
        corrected_text = response.content.strip()
        if corrected_text != question:
            logging.info(f"Запрос пользователя скорректирован: '{question}' -> '{corrected_text}'")
        return corrected_text
    except Exception as e:
        logging.error(f"Ошибка при коррекции запроса: {e}")
        return question


# # --- AI-КЛАССИФИКАТОР ---
# def _load_keywords() -> str:
#     try:
#         with open(KEYWORDS_PATH, 'r', encoding='utf-8') as f:
#             return f.read().strip()
#     except Exception:
#         logging.error(f"Не удалось загрузить ключевые слова из {KEYWORDS_PATH}")
#         return ""

#RELEVANT_KEYWORDS_LIST = _load_keywords()


async def is_query_relevant_ai(question: str, history: List[Dict[str, str]]) -> bool:
    """
    Использует LLM с few-shot промптом для точной бинарной классификации релевантности запроса.
    """
    if not gigachat:
        logging.warning("Пропуск проверки релевантности (сервис GigaChat недоступен). Разрешаем запрос.")
        return True  # В случае сбоя лучше пропустить запрос, чем блокировать пользователя

    last_assistant_message = ""
    if history and len(history) > 1 and history[-2]["role"] == "assistant":
        last_assistant_message = history[-2]["content"]

    # Формируем полный промпт для модели
    full_prompt = (
        f"{CLASSIFIER_PROMPT}\n\n"
        f"--- ДИАЛОГ ДЛЯ АНАЛИЗА ---\n"
        f"Последняя фраза ассистента: '{last_assistant_message}'\n"
        f"Новый запрос пользователя: '{question}'\n"
        f"--- КОНЕЦ ДИАЛОГА ---\n\n"
        f"Вопрос: Является ли новый запрос пользователя релевантным тематике школы? Ответь 'да' или 'нет'."
    )

    try:
        response = await gigachat.ainvoke([SystemMessage(content=full_prompt)], max_tokens=3)
        answer = response.content.strip().lower()
        logging.info(f"AI-классификатор ответил: '{answer}' для запроса '{question}'")
        return "да" in answer
    except Exception as e:
        logging.error(f"Ошибка при проверке релевантности: {e}. Разрешаем запрос по умолчанию.")
        return True # При любой ошибке лучше пропустить
    
    
# --- AI-ГЕНЕРАТОР ---
def _build_prompt(context: str, history: List[Dict[str, str]], context_key: str = "default") -> List[BaseMessage]:
    """
    Формирует промпт, добавляя в него указание на текущий контекст.
    """
    full_system_prompt = f"{SYSTEM_PROMPT}\n\n"

    # Добавляем AI прямое указание, на чем фокусироваться
    if context_key == "course_junior":
        full_system_prompt += "ВАЖНОЕ УКАЗАНИЕ: Клиент интересуется курсом для младшей группы (9-13 лет). Сосредоточь все ответы ИСКЛЮЧИТЕЛЬНО на этом курсе. Не упоминай другие курсы.\n\n"
    elif context_key == "course_senior":
        full_system_prompt += "ВАЖНОЕ УКАЗАНИЕ: Клиент интересуется курсом для старшей группы (14-17 лет). Сосредоточь все ответы ИСКЛЮЧИТЕЛЬНО на этом курсе. Не упоминай другие курсы.\n\n"

    full_system_prompt += (
        f"Опираясь на предоставленный ниже контекст, ответь на следующий вопрос пользователя.\n"
        f"--- КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ---\n"
        f"{context}\n"
        f"--- КОНЕЦ КОНТЕКСТА ---"
    )
    
    messages: List[BaseMessage] = [SystemMessage(content=full_system_prompt)]
    
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
            
    return messages

async def get_llm_response(question: str, history: List[Dict[str, str]], context_key: str = "default") -> str:
    """
    Получает развернутый ответ от "умной" LLM, учитывая контекст диалога.
    """
    if not gigachat:
        return "Извините, сервис временно недоступен."

    try:
        # Шаг 1: Находим релевантные знания в документах
        docs = await vectorstore.asimilarity_search(question, k=3)
        context = "\n---\n".join([doc.page_content for doc in docs]) if docs else "Информация по данному вопросу в базе знаний отсутствует."

        # Шаг 2: Формируем правильный промпт, передавая контекст
        prompt_messages = _build_prompt(context, history, context_key)
        prompt_messages.append(HumanMessage(content=question))
        
        # Шаг 3: Делаем запрос к AI
        logging.info(f">>> Отправка запроса к GigaChat с контекстом '{context_key}'...")
        response = await gigachat.ainvoke(prompt_messages)
        
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata:
            prompt_tokens = usage_metadata.get('prompt_tokens', 0)
            completion_tokens = usage_metadata.get('completion_tokens', 0)
            total_tokens = usage_metadata.get('total_tokens', 0)
            logging.info(
                f"<<< Получен ответ. Токены: {prompt_tokens} (запрос) + {completion_tokens} (ответ) = {total_tokens} (всего)"
            )
        else:
            logging.warning("Метаданные о токенах не найдены в ответе GigaChat.")
        
        return response.content.strip()
        
    except Exception as e:
        logging.error(f"Ошибка при обращении к GigaChat: {e}", exc_info=True)
        return "К сожалению, произошла техническая ошибка. Пожалуйста, попробуйте позже."

