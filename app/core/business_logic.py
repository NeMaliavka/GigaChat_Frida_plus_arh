import json
from pathlib import Path
from typing import Dict, Any
import pymorphy3 # Импортируем библиотеку для работы с морфологией

# --- Код движка правил (без изменений) ---
RULES_PATH = Path(__file__).parent.parent / "knowledge_base" / "rules" / "business_rules.json"
try:
    with open(RULES_PATH, 'r', encoding='utf-8') as f:
        BUSINESS_RULES = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    BUSINESS_RULES = {"rules": [], "default_outcome": {}}

# Инициализируем морфологический анализатор
morph = pymorphy3.MorphAnalyzer()

def _check_condition(condition: Dict, data: Dict) -> bool:
    """Универсальная функция для проверки одного условия."""
    key_to_check = condition.get("key")
    condition_type = condition.get("type")
    condition_value = condition.get("value")
    
    user_value_str = str(data.get(key_to_check, ''))
    
    if not user_value_str.isdigit():
        return False
        
    user_value_int = int(user_value_str)

    if condition_type == "range":
        min_val, max_val = condition_value
        return min_val <= user_value_int <= max_val
    elif condition_type == "less_than":
        return user_value_int < condition_value
    elif condition_type == "greater_than":
        return user_value_int > condition_value
        
    return False

def process_final_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Универсальный "движок правил", который теперь правильно
    склоняет имя ребенка для финального предложения.
    """
    processed_data = data.copy()

    # --- Применение бизнес-правил (без изменений) ---
    for rule in BUSINESS_RULES.get("rules", []):
        if _check_condition(rule.get("condition", {}), processed_data):
            action = rule.get("action", {})
            action_type = action.get("type")
            
            if action_type == "set_outcome":
                processed_data[action.get("key")] = action.get("value")
            
            elif action_type == "return_message":
                processed_data[action.get("key")] = action.get("value")
                processed_data.pop("course_name", None) 
                return processed_data
    
    default_outcome = BUSINESS_RULES.get("default_outcome", {})
    if default_outcome and default_outcome.get("key") not in processed_data:
        processed_data[default_outcome.get("key")] = default_outcome.get("value")

    # --- НАЧАЛО ИСПРАВЛЕННОГО БЛОКА ---
    
    # Обрабатываем имя ребенка
    child_name = processed_data.get("child_name", "")
    if child_name:
        # Находим первую (наиболее вероятную) форму слова
        parsed_name = morph.parse(child_name)[0]
        # Пытаемся получить дательный падеж ('кому?'), если его нет - именительный
        dative_name = parsed_name.inflect({'datv'}) or parsed_name.inflect({'nomn'})
        
        if dative_name:
            processed_data['child_name_dative'] = dative_name.word.capitalize()
        else:
            processed_data['child_name_dative'] = child_name.capitalize()
    else:
        processed_data['child_name_dative'] = "Вашему ребенку"

    # Обрабатываем имя родителя (просто делаем первую букву заглавной)
    parent_name = processed_data.get("parent_name", "")
    processed_data['parent_name_capitalized'] = parent_name.capitalize() if parent_name else "Уважаемый родитель"
        
    # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

    return processed_data
