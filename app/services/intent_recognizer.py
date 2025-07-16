# app/services/intent_recognizer.py

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from app.utils.loaders import load_keywords_from_yaml

class IntentRecognizer:
    """
    Сервис для распознавания намерений пользователя с помощью семантического поиска.
    """
    def __init__(self, keywords_path: str, model_name: str = 'all-MiniLM-L6-v2', threshold: float = 0.75):
        """
        Инициализирует распознаватель, загружает ключевые слова и создает эмбеддинги.
        
        :param keywords_path: Путь к YAML-файлу с ключевыми словами.
        :param model_name: Название модели SentenceTransformer.
        :param threshold: Порог схожести для определения интента.
        """
        self.threshold = threshold
        self.model = SentenceTransformer(model_name)
        self.intents_data = self._load_and_embed_keywords(keywords_path)
        logging.info("Сервис IntentRecognizer успешно инициализирован.")

    def _load_and_embed_keywords(self, path: str) -> Dict[str, np.ndarray]:
        """Загружает ключевые слова и преобразует их в эмбеддинги."""
        keywords_by_intent = load_keywords_from_yaml(path)
        embedded_intents = {}
        
        for intent, phrases in keywords_by_intent.items():
            if phrases:
                try:
                    embeddings = self.model.encode(phrases, convert_to_tensor=False)
                    embedded_intents[intent] = embeddings
                    logging.info(f"Для интента '{intent}' создано {len(phrases)} эмбеддингов.")
                except Exception as e:
                    logging.error(f"Ошибка при создании эмбеддингов для интента '{intent}': {e}")
        return embedded_intents

    def get_intent(self, query: str) -> Optional[str]:
        """
        Определяет интент запроса, находя ближайшее семантическое соответствие.

        :param query: Текст запроса пользователя.
        :return: Название интента или None, если схожесть ниже порога.
        """
        if not self.intents_data:
            logging.warning("Нет загруженных интентов для распознавания.")
            return None
        
        query_embedding = self.model.encode([query])
        max_similarity = 0.0
        best_intent = None

        for intent, intent_embeddings in self.intents_data.items():
            similarities = cosine_similarity(query_embedding, intent_embeddings)[0]
            current_max_sim = np.max(similarities)
            
            if current_max_sim > max_similarity:
                max_similarity = current_max_sim
                best_intent = intent
        
        if max_similarity >= self.threshold:
            logging.info(f"Обнаружен интент '{best_intent}' с уверенностью {max_similarity:.2f} для запроса: '{query}'")
            return best_intent
        
        logging.info(f"Для запроса '{query}' не найдено подходящего интента (макс. схожесть: {max_similarity:.2f})")
        return None

# Создаем один экземпляр сервиса для всего приложения (Singleton)
# Путь к файлу нужно будет указать в вашем config.py
intent_recognizer_service = IntentRecognizer(keywords_path="config/keywords.yaml")
