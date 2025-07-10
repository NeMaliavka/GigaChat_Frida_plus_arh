import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()


# Настройка SSL-сертификата (если необходимо)
CERT_FILENAME = "russian_trusted_root_ca.cer"
cert_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), CERT_FILENAME)
if os.path.exists(cert_path):
    os.environ["SSL_CERT_FILE"] = cert_path
else:
    # В Docker-контейнере этого файла может не быть, это нормально
    logging.warning(f"SSL-сертификат не найден по пути: {cert_path}")


# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("OWNER_CHAT_ID", "0"))

# --- GigaChat ---
SBERCLOUD_API_KEY = os.getenv("SBERCLOUD_API_KEY")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-Pro")
GIGACHAT_MAX_TOKENS = int(os.getenv("GIGACHAT_MAX_TOKENS", "1024"))

# --- Базы данных ---
DB_PATH = os.getenv("DB_PATH", "db/chat_history.db")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "db/chroma_db")
# --- Переменная для подключения к базе данных ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Окружение и логирование ---
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- CRM Bitrix24 (опционально) ---
BITRIX24_WEBHOOK_URL = os.getenv("BITRIX24_WEBHOOK_URL")
BITRIX24_RESPONSIBLE_ID = int(os.getenv("BITRIX24_RESPONSIBLE_ID", "1"))
TEACHER_IDS = int(os.getenv("TEACHER_IDS"))
GROUP_ID = int(os.getenv("GROUP_ID"))


# --- Пути к файлам знаний ---
PROMPT_PATH = os.getenv("PROMPT_PATH", "app/knowledge_base/documents/lor.txt")
TEMPLATES_PATH = os.getenv("TEMPLATES_PATH", "app/knowledge_base/documents/templates.py")
KEYWORDS_PATH="app/knowledge_base/documents/keywords.txt"
DISTANCE_THRESHOLD = 0.9 


# --- Валидация обязательных переменных ---
if not TELEGRAM_BOT_TOKEN or not SBERCLOUD_API_KEY:
    raise ValueError(
        "Ключевые переменные окружения TELEGRAM_BOT_TOKEN и SBERCLOUD_API_KEY должны быть установлены в .env файле."
    )

# Настройка уровня логирования на основе переменной из .env
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

logging.info("Конфигурация успешно загружена.")
if ENVIRONMENT == "development":
    logging.warning("Приложение запущено в режиме разработки.")
