# app/utils/loaders.py

import logging
import yaml  # <--- Импортируем YAML
from pathlib import Path
from typing import Dict, List, Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def load_keywords_from_yaml(filename: str = "config/keywords.yaml") -> Dict[str, List[str]]:
    """
    Загружает ключевые слова из структурированного YAML-файла.
    Возвращает словарь, где ключ - это интент (например, 'cancellation'),
    а значение - список ключевых слов.
    """
    filepath = BASE_DIR / filename
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            keywords_data = yaml.safe_load(f)
        
        if not isinstance(keywords_data, dict):
            logging.warning(f"Файл '{filename}' имеет некорректную структуру. Ожидался словарь.")
            return {}
            
        logging.info(f"Успешно загружены ключевые слова из '{filename}'. Интенты: {list(keywords_data.keys())}")
        return keywords_data

    except FileNotFoundError:
        logging.warning(f"Файл с ключевыми словами '{filename}' не найден. Будет использован пустой словарь.")
        return {}
    except Exception as e:
        logging.error(f"Ошибка при чтении файла с ключевыми словами '{filename}': {e}")
        return {}


