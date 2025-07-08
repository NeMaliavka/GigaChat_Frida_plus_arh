import re
from pymorphy3 import MorphAnalyzer

morph = MorphAnalyzer()

def correct_keyboard_layout(text: str) -> str | None:
    """
    Переключает текст с английской раскладки на русскую, корректно
    обрабатывая символы в верхнем и нижнем регистре (с Shift и без).
    """
    # Полная карта символов для английской и русской раскладок
    eng = "`" + "qwertyuiop[]asdfghjkl;'zxcvbnm,./" + '~' + 'QWERTYUIOP{}ASDFGHJKL:"ZXCVBNM<>?'
    rus = "ё" + "йцукенгшщзхъфывапролджэячсмитьбю." + 'Ё' + 'ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,'

    # Создаем таблицу для перевода
    layout_map = str.maketrans(eng, rus)
    
    # Переводим текст
    corrected_text = text.translate(layout_map)
    
    # Если текст не изменился или в нем не появились русские буквы,
    # значит, коррекция не требуется или невозможна.
    if corrected_text == text or not re.search(r'[а-яА-ЯёЁ]', corrected_text):
        return None
        
    return corrected_text

def is_plausible_name(name: str) -> bool:
    """
    Проверяет, является ли строка похожей на реальное имя.
    Отсеивает цифры, спецсимволы, слишком короткие/длинные строки и стоп-слова.
    """
    name = name.strip()
    
    # 1. Проверка длины
    if not (2 <= len(name) <= 50):
        return False
        
    # 2. Проверка на содержание ТОЛЬКО букв, пробелов или дефисов
    if not re.fullmatch(r'[а-яА-ЯёЁ\s\-]+', name):
        return False
        
    # 3. Проверка на стоп-слова
    stop_words = ["тест", "проверка", "бот", "дурак", "абырвалг", "йцукен"]
    if name.lower() in stop_words:
        return False

    return True

def inflect_name(name: str, case: str) -> str:
    """
    Склоняет имя (или ФИО) в нужный падеж, стараясь выбрать правильную форму.
    """
    try:
        words = name.split()
        is_capitalized = [word[0].isupper() for word in words]

        inflected_parts = []
        for i, part in enumerate(words):
            # Ищем разбор слова как имени или фамилии
            parses = morph.parse(part.lower())
            name_parse = next((p for p in parses if 'Name' in p.tag or 'Surn' in p.tag), parses[0])
            
            # Приводим к единственному числу перед склонением
            singular_form = name_parse.inflect({'sing'})
            if singular_form:
                name_parse = singular_form

            inflected_word_obj = name_parse.inflect({case})
            
            if inflected_word_obj:
                inflected_word = inflected_word_obj.word
                # Восстанавливаем капитализацию
                if is_capitalized[i]:
                    inflected_parts.append(inflected_word.capitalize())
                else:
                    inflected_parts.append(inflected_word)
            else:
                inflected_parts.append(words[i])
            
        return " ".join(inflected_parts)
    except Exception:
        # В случае любой ошибки, просто возвращаем исходное имя с капитализацией
        return name.capitalize()

