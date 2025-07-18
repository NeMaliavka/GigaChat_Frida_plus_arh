# app/utils/formatters.py

import logging
import re
from datetime import datetime

# Словарь для склонения названий месяцев в родительном падеже
MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}
WEEKDAYS_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
    4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}

try:
    from app.utils.text_tools import inflect_name
    MORPHOLOGY_ENABLED = True
except ImportError:
    logging.warning("Утилиты морфологии (text_tools.py) не найдены.")
    MORPHOLOGY_ENABLED = False
    def inflect_name(name: str, _: str) -> str: return name

def format_response_with_inflection(template: str, data: dict) -> str:
    """
    Надежно форматирует строку: сначала склоняет имена, а затем подставляет остальные данные.
    Ищет плейсхолдеры вида {child_name:datv} и простые {parent_name}.
    """
    if not template: return ""

    processed_template = template

    if MORPHOLOGY_ENABLED:
        # Шаг 1: Найти все плейсхолдеры для склонения (например, {child_name:datv})
        inflection_placeholders = re.findall(r'\{(\w+):(\w+)\}', template)
        
        for var_name, case in inflection_placeholders:
            placeholder_to_replace = f"{{{var_name}:{case}}}"
            
            # Получаем оригинальное значение (например, "Татьяна")
            original_value = data.get(var_name, "")
            
            # Склоняем его (например, в "Татьяне")
            inflected_value = inflect_name(str(original_value), case)
            
            # Заменяем в шаблоне
            processed_template = processed_template.replace(placeholder_to_replace, inflected_value)

    # Шаг 2: Форматируем оставшиеся простые плейсхолдеры (например, {parent_name})
    try:
        # Используем стандартный .format() с исходными данными
        return processed_template.format(**data)
    except KeyError as e:
        logging.warning(f"В шаблоне не хватило данных для ключа: {e}. Шаблон: '{processed_template}'")
        # Возвращаем частично отформатированный шаблон, чтобы не падать с ошибкой
        return processed_template

def format_date_russian(dt: datetime, mode: str = 'full') -> str:
    """
    Форматирует объект datetime в красивую русскую строку.

    Args:
        dt (datetime): Объект даты и времени.
        mode (str): Режим форматирования:
                    'full' -> "17 июля (Четверг) в 17:00"
                    'short' -> "17 июля в 17:00"

    Returns:
        str: Отформатированная строка.
    """
    if not isinstance(dt, datetime):
        logging.error(f"В format_date_russian передан неверный тип: {type(dt)}")
        return "Некорректная дата"

    day = dt.day
    month = MONTHS_RU.get(dt.month, "")
    weekday = WEEKDAYS_RU.get(dt.weekday(), "")
    time_str = dt.strftime('%H:%M')

    if mode == 'full':
        return f"{day} {month} ({weekday}) в {time_str}"
    
    elif mode == 'short':
        return f"{day} {month} в {time_str}"
    
    return dt.strftime('%d.%m.%Y %H:%M')


# --- ВОТ ВОССТАНОВЛЕННАЯ ФУНКЦИЯ ---
def get_user_data_summary(user_data: dict, for_bitrix: bool = False) -> str:
    """
    Формирует красивую сводку по анкете пользователя для отправки в Telegram или Bitrix24.
    """
    # Безопасно извлекаем данные, подставляя "не указано" если их нет
    parent_name = user_data.get('q1', "не указано")
    child_name = user_data.get('q2', "не указано")
    child_age = user_data.get('q3', "не указано")
    child_interests = user_data.get('q4', "не указаны")
    username = user_data.get('username', "N/A")

    if for_bitrix:
        # Формат для описания задачи в Bitrix24
        return (
            f"Новая заявка на пробный урок от @{username}.\n\n"
            f"[B]Родитель:[/B] {parent_name}\n"
            f"[B]Ученик:[/B] {child_name}\n"
            f"[B]Возраст ученика:[/B] {child_age}\n"
            f"[B]Увлечения:[/B] {child_interests}\n\n"
            f"[B]Как связаться:[/B] через Telegram (@{username})"
        )
    else:
        # Формат для подтверждающего сообщения в Telegram
        # Этот формат больше не используется, но мы оставляем его для полноты
        return (
            f"Отлично, давайте всё проверим:\n\n"
            f"🙋‍♂️ **Родитель:** {parent_name}\n"
            f"👶 **Ученик:** {child_name}, {child_age} лет\n"
            f"🎮 **Интересы:** {child_interests}"
        )
# --- КОНЕЦ ВОССТАНОВЛЕННОГО БЛОКА ---
