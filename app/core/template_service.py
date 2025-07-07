import random
from typing import List, Tuple, Optional, Dict
from thefuzz import fuzz

# Импортируем новую, вложенную структуру шаблонов
from app.knowledge_base.documents.templates import TEMPLATES

SIMILARITY_THRESHOLD = 90

def find_template(user_text: str, context_key: str = "default") -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Находит шаблон, сначала ища в "ящике" для конкретного контекста,
    а затем — в "общем" ящике.
    """
    lower_user_text = user_text.lower()

    # 1. Сначала ищем в контекстном "ящике" (например, "course_junior")
    context_templates = TEMPLATES.get(context_key, {})
    for key, value in context_templates.items():
        template_phrases = key.split('/')
        for phrase in template_phrases:
            if fuzz.token_set_ratio(lower_user_text, phrase.lower()) >= SIMILARITY_THRESHOLD:
                return key, value
    
    # 2. Если не нашли, ищем в "общем" ящике
    common_templates = TEMPLATES.get("common", {})
    for key, value in common_templates.items():
        template_phrases = key.split('/')
        for phrase in template_phrases:
            if fuzz.token_set_ratio(lower_user_text, phrase.lower()) >= SIMILARITY_THRESHOLD:
                return key, value

    # Если ничего не найдено
    return None, None

def choose_variant(variants: List[str]) -> str:
    """Выбирает случайный вариант ответа из списка."""
    if not variants:
        return ""
    return random.choice(variants)
