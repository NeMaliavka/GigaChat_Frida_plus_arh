import random
import re
# ИСПРАВЛЕНО: Добавляем Tuple в импорты
from typing import Any, Dict, List, Tuple
import importlib.util
from thefuzz import fuzz

from app.config import TEMPLATES_PATH

def load_templates(path: str):
    """Динамически загружает шаблоны из Python файла."""
    try:
        spec = importlib.util.spec_from_file_location("templates", path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, "TEMPLATES", {})
        else:
            print(f"Ошибка: не удалось создать spec для {path}")
            return {}
    except Exception as e:
        print(f"Ошибка загрузки шаблонов: {e}")
        return {}

TEMPLATES = load_templates(TEMPLATES_PATH)
REGEX_CACHE: Dict[str, re.Pattern] = {}

def find_template(text: str) -> Tuple[str | None, Any]:
    """
    Находит подходящий шаблон и его ключ по тексту пользователя.
    Возвращает (ключ, значение) или (None, None).
    """
    lower_text = text.lower()
    for keys, value in TEMPLATES.items():
        # Проверяем, что keys - это строка, а не что-то другое
        if not isinstance(keys, str):
            continue
            
        for key in keys.split('/'):
            key_clean = key.strip()
            # Убеждаемся, что ключ не пустой
            if not key_clean:
                continue
            
            if fuzz.token_set_ratio(key_clean, lower_text) > 80:
                return keys, value
    return None, None

def choose_variant(candidate: Any, history: List[Dict[str, str]]) -> str:
    """Выбирает один из вариантов ответа, избегая повторений."""
    if not isinstance(candidate, list):
        return str(candidate)
    
    assistant_responses = {m["content"] for m in history if m["role"] == "assistant"}
    available_options = [var for var in candidate if var not in assistant_responses]
    
    if available_options:
        return random.choice(available_options)
    
    return random.choice(candidate)

