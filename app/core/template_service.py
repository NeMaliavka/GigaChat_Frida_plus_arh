import random
import logging
from typing import List, Dict, Tuple
# Импортируем функцию для подсчета учеников
from app.db.database import get_enrolled_student_count

# Предполагается, что ваш файл templates.py находится здесь
# и в нем есть переменная TEMPLATES
try:
    from app.knowledge_base.documents.templates import TEMPLATES
except ImportError:
    logging.error("Не удалось импортировать TEMPLATES из app.knowledge_base.documents.templates")
    TEMPLATES = {}


def find_template_by_keywords(user_text: str) -> Tuple[str | None, dict | list | None]:
    user_text_lower = user_text.lower()
    for keys, template_data in TEMPLATES.items():
        keywords = [key.strip() for key in keys.split('/')]
        if any(keyword in user_text_lower for keyword in keywords):
            return keys, template_data
    return None, None

async def build_template_response(template_data: dict | list, history: List[Dict], user_data: dict) -> str:
    """
    Собирает "умный" ответ из шаблона, анализируя историю, данные пользователя и счетчик учеников.
    """
    print("!!! ЗАПУЩЕНА ПРАВИЛЬНАЯ ВЕРСИЯ build_template_response ИЗ TEMPLATE_SERVICE !!!")
    if isinstance(template_data, list):
        return random.choice(template_data)
    
    if isinstance(template_data, dict):
        response_parts = []
        
        # Получаем количество учеников
        enrolled_count = await get_enrolled_student_count()
        is_promo_active = enrolled_count < 100
        
        is_dialog_start = len(history) <= 4 

        if is_dialog_start and (greetings := template_data.get("greeting")):
            response_parts.append(random.choice(greetings))

        # Выбираем тело ответа в зависимости от акции
        if is_promo_active:
            response_parts.append(template_data.get("body_promo_active") or template_data.get("body"))
        else:
            response_parts.append(template_data.get("body_promo_ended") or template_data.get("body"))
        
        if follow_ups := template_data.get("follow_up"):
            response_parts.append(random.choice(follow_ups))

        # Собираем финальный текст и форматируем его с данными пользователя
        full_response = "\n\n".join(filter(None, response_parts))
        
        # Капитализируем имя и отчество
        if 'parent_name' in user_data:
            user_data['parent_name'] = " ".join(word.capitalize() for word in user_data['parent_name'].split())
            
        return full_response.format(**user_data)
    
    return "Не удалось сформировать ответ по шаблону."

def find_template_by_keywords(user_text: str) -> Tuple[str | None, dict | list | None]:
    """
    Находит наиболее подходящий шаблон по ключевым словам.
    Ключи словаря TEMPLATES теперь могут содержать несколько ключевых слов через '/'.
    """
    user_text_lower = user_text.lower()
    for keys, template_data in TEMPLATES.items():
        # Разделяем строку с ключами на отдельные ключевые слова
        keywords = [key.strip() for key in keys.split('/')]
        if any(keyword in user_text_lower for keyword in keywords):
            return keys, template_data
    return None, None
