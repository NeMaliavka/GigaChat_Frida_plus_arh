import logging
from typing import List

from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage

from app.config import SBERCLOUD_API_KEY, GIGACHAT_MODEL, GIGACHAT_MAX_TOKENS
from app.knowledge_base.loader import vectorstore, SYSTEM_PROMPT

# Инициализация модели GigaChat
try:
    gigachat = GigaChat(
        credentials=SBERCLOUD_API_KEY,
        scope="GIGACHAT_API_PERS",
        model=GIGACHAT_MODEL,
        max_tokens=GIGACHAT_MAX_TOKENS,
        verify_ssl_certs=False,
    )
    logging.info(f"Модель GigaChat '{GIGACHAT_MODEL}' успешно инициализирована.")
except Exception as e:
    logging.error(f"Ошибка инициализации GigaChat: {e}", exc_info=True)
    gigachat = None

def _build_prompt(context: str, history: List[dict]) -> List[BaseMessage]:
    """
    Формирует промпт для GigaChat с учетом строгих инструкций, истории и контекста.
    """
    try:
        prompt_template = SYSTEM_PROMPT.format(context=context)
    except KeyError:
        logging.warning("В системном промпте отсутствует плейсхолдер '{context}'.")
        prompt_template = SYSTEM_PROMPT + "\n\nКонтекст:\n" + context

    messages: List[BaseMessage] = [SystemMessage(content=prompt_template)]
    
    # Добавляем историю диалога. Последнее сообщение пользователя уже в history.
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
            
    return messages

def get_llm_response(question: str, history: List[dict]) -> str:
    """
    Получает ответ от LLM, используя RAG с порогом релевантности, и логирует расход токенов.
    """
    if not gigachat:
        return "Извините, сервис временно недоступен из-за проблем с подключением к нейросети."

    try:
        # 1. Поиск документов с оценкой релевантности (L2-дистанция)
        DISTANCE_THRESHOLD = 0.8  # Порог. Чем меньше, тем более похожи.
        
        docs_with_scores = vectorstore.similarity_search_with_score(question, k=3)
        logging.info(f"Найденные документы с оценками (дистанция): {docs_with_scores}")

        # 2. Фильтрация документов по порогу
        relevant_docs = [doc for doc, score in docs_with_scores if score < DISTANCE_THRESHOLD]

        # 3. Формирование контекста для AI
        if not relevant_docs:
            logging.warning(f"Релевантный контекст не найден (оценка выше порога {DISTANCE_THRESHOLD}). Ответ будет сгенерирован без контекста.")
            context = "Информация по данному вопросу в базе знаний отсутствует."
        else:
            best_score = docs_with_scores[0][1]
            logging.info(f"Найден релевантный контекст. Лучшая оценка: {best_score}")
            context = "\n---\n".join([doc.page_content for doc in relevant_docs])

        # 4. Формирование полного промпта
        # Передаем историю, в которой уже есть последний вопрос пользователя
        prompt_messages = _build_prompt(context, history)
        
        # 5. Запрос к GigaChat и логирование токенов
        logging.info(">>> Отправка запроса к GigaChat...")
        response = gigachat.invoke(prompt_messages)
        
        response_text = response.content.strip()
        usage_metadata = response.usage_metadata
        
        if usage_metadata:
            prompt_tokens = usage_metadata.get('prompt_tokens', 0)
            completion_tokens = usage_metadata.get('completion_tokens', 0)
            total_tokens = usage_metadata.get('total_tokens', 0)
            
            logging.info(
                f"<<< Получен ответ от GigaChat. "
                f"Токены запроса: {prompt_tokens}, "
                f"Токены ответа: {completion_tokens}, "
                f"Всего: {total_tokens}"
            )
        else:
            logging.warning("Метаданные о токенах не найдены в ответе GigaChat.")
        
        return response_text
        
    except Exception as e:
        logging.error(f"Ошибка при обращении к GigaChat: {e}", exc_info=True)
        return "К сожалению, произошла техническая ошибка. Пожалуйста, попробуйте позже."
