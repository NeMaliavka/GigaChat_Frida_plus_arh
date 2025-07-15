# app/utils/formatters.py
import re
import logging
from datetime import datetime

# Импортируем утилиты, обрабатывая возможное их отсутствие
try:
    from app.utils.text_tools import inflect_name
    MORPHOLOGY_ENABLED = True
except ImportError:
    logging.warning("Утилиты (text_tools.py) не найдены. Расширенные функции будут отключены.")
    MORPHOLOGY_ENABLED = False
    def inflect_name(name: str, _: str) -> str: return name


def format_response_with_inflection(template: str, data: dict) -> str:
    """Форматирует строку, склоняя имена и корректно капитализируя их."""
    if not MORPHOLOGY_ENABLED or not template:
        # Простая обработка для случая, если нет user_data
        return template.format(**data) if template else ""

    def repl(match):
        var_name, case = match.groups()
        # Получаем значение из данных, если его нет - пустая строка
        value_to_inflect = data.get(var_name, "")
        # Если значение не строка (например, число), преобразуем его
        return inflect_name(str(value_to_inflect), case)

    processed_template = re.sub(r'\{(\w+):(\w+)\}', repl, template)

    final_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            final_data[key] = " ".join(word.capitalize() for word in value.split())
        else:
            final_data[key] = value

    return processed_template.format(**final_data)


def format_date_russian(dt: datetime, format_type: str = 'full') -> str:
    """
    Надежно форматирует дату на русском языке, не завися от системной локали.
    """
    months_gent = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]

    weekdays = [
        "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"
    ]

    if format_type == 'full':
        # Формат для кнопок: "11 июля (Пятница)"
        return f"{dt.day} {months_gent[dt.month - 1]} ({weekdays[dt.weekday()]})"
    elif format_type == 'short':
        # Формат для подтверждения: "11 июля в 17:00"
        return f"{dt.day} {months_gent[dt.month - 1]} в {dt.strftime('%H:%M')}"
    
    return dt.strftime('%Y-%m-%d %H:%M') # Возврат по умолчанию
