import os
import logging
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_chroma import Chroma
from sentence_transformers import SentenceTransformer

from app.config import CHROMA_DB_PATH, PROMPT_PATH

# Пути к файлам с информацией о проекте
DOCUMENTS_PATHS = [
    "app/knowledge_base/documents/project_info.pdf",
    "app/knowledge_base/documents/lor.txt"
]

class FridaEmbeddings:
    """Класс-обертка для модели эмбеддингов FRIDA."""
    def __init__(self, model_name: str = "ai-forever/FRIDA"):
        self.model = SentenceTransformer(model_name)

    def embed_query(self, text: str) -> List[float]:
        """Создает эмбеддинг для поискового запроса."""
        return self.model.encode(f"search_query: {text}", normalize_embeddings=True).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Создает эмбеддинги для документов."""
        return [
            self.model.encode(f"search_document: {t}", normalize_embeddings=True).tolist()
            for t in texts
        ]

def load_documents():
    """Загружает документы из разных источников (PDF, TXT)."""
    docs = []
    for path in DOCUMENTS_PATHS:
        if path.endswith(".pdf"):
            loader = PyPDFLoader(path)
        elif path.endswith(".txt"):
            loader = TextLoader(path, encoding="utf-8")
        else:
            logging.warning(f"Неподдерживаемый формат файла: {path}")
            continue
        docs.extend(loader.load())
    return docs

def get_vectorstore():
    """
    Создает или загружает векторную базу данных.
    Индексирует документы при первом запуске.
    """
    embeddings = FridaEmbeddings()
    
    if not os.path.exists(CHROMA_DB_PATH):
        logging.info("Создание новой векторной базы ChromaDB...")
        documents = load_documents()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(documents)
        
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=CHROMA_DB_PATH
        )
        logging.info("Векторная база успешно создана и сохранена.")
    else:
        logging.info("Загрузка существующей векторной базы ChromaDB...")
        vectorstore = Chroma(
            persist_directory=CHROMA_DB_PATH,
            embedding_function=embeddings
        )
    return vectorstore

# Инициализируем один раз при старте
vectorstore = get_vectorstore()
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

def read_system_prompt() -> str:
    """Читает системный промпт из файла."""
    try:
        with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"Файл системного промпта не найден: {PROMPT_PATH}")
        return "Ты — полезный ассистент."

SYSTEM_PROMPT = read_system_prompt() + """--- СПЕЦИАЛЬНЫЕ КОМАНДЫ ---
Если пользователь явно выражает желание записаться на пробный урок, 
начать запись, выбрать время или что-то подобное, 
твой ЕДИНСТВЕННЫЙ ответ должен быть специальной командой: [START_ENROLLMENT].
Если пользователь явно выражает желание отменить существующую запись, пробный 
урок или встречу, ответь только одной командой: [CANCEL_BOOKING]. 
Не пиши ничего, кроме этих команд. Во всех остальных случаях веди диалог как обычно."""

