import logging
import yaml
from pathlib import Path
from typing import Dict, Optional, List
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Вспомогательная функция для загрузки, вы можете использовать свою, если она есть
def load_keywords_from_yaml(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Не удалось загрузить YAML файл по пути: {path}. Ошибка: {e}")
        return {}

class IntentRecognizer:
    """
    Гибридный сервис для распознавания намерений: сначала по правилам, затем по семантике.
    Использует единый YAML-файл как источник правды.
    """
    def __init__(self, keywords_path: str, model_name: str = 'all-MiniLM-L6-v2', threshold: float = 0.75):
        self.threshold = threshold
        self.model = SentenceTransformer(model_name)
        
        # Загружаем полную структуру из YAML
        self.intents_data = load_keywords_from_yaml(keywords_path)
        
        # Создаем эмбеддинги только на основе текстовых ключевых слов
        self.intents_embeddings = self._create_embeddings(self.intents_data)
        
        logging.info("Сервис IntentRecognizer успешно инициализирован с гибридной моделью.")

    def _create_embeddings(self, intents_data: Dict[str, Dict]) -> Dict[str, np.ndarray]:
        """
        Создает эмбеддинги для семантического поиска, теперь работает с новой структурой YAML.
        """
        embedded_intents = {}
        for intent, data in intents_data.items():
            # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
            # Мы извлекаем список ключевых слов из ключа 'keywords'
            phrases = data.get('keywords', [])
            
            if phrases and isinstance(phrases, list):
                try:
                    embeddings = self.model.encode(phrases, convert_to_tensor=False)
                    embedded_intents[intent] = embeddings
                except Exception as e:
                    logging.error(f"Ошибка при создании эмбеддингов для интента '{intent}': {e}")
        return embedded_intents

    def _get_intent_by_rule(self, query: str) -> Optional[str]:
        """
        Первый слой: ищет точное вхождение ключевых фраз.
        """
        query_lower = query.lower()
        for intent, data in self.intents_data.items():
            # Ищем в списке 'keywords'
            for phrase in data.get('keywords', []):
                if phrase.lower() in query_lower:
                    logging.info(f"Интент '{intent}' определен по строгому правилу (фраза: '{phrase}').")
                    return intent
        return None

    def _get_intent_by_semantic(self, query: str) -> Optional[str]:
        """
        Второй слой: определяет интент с помощью семантического поиска.
        """
        if not self.intents_embeddings: return None
        
        query_embedding = self.model.encode([query])
        max_similarity = 0.0
        best_intent = None

        for intent, intent_embeddings in self.intents_embeddings.items():
            similarities = cosine_similarity(query_embedding, intent_embeddings)[0]
            current_max_sim = np.max(similarities)
            
            if current_max_sim > max_similarity:
                max_similarity = current_max_sim
                best_intent = intent

        if max_similarity >= self.threshold:
            logging.info(f"Интент '{best_intent}' определен через семантику (схожесть: {max_similarity:.2f})")
            return best_intent
            
        return None

    def get_intent(self, query: str) -> Optional[str]:
        """
        Главная функция: сначала правила, потом семантика.
        """
        rule_based_intent = self._get_intent_by_rule(query)
        if rule_based_intent:
            return rule_based_intent
            
        return self._get_intent_by_semantic(query)

# Создаем единый экземпляр сервиса для всего приложения
intent_recognizer_service = IntentRecognizer(keywords_path="config/keywords.yaml")