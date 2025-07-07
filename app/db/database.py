import logging
from typing import List, Dict

from sqlalchemy import select, update, desc, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import DATABASE_URL
from app.db.models import Base, User, DialogHistory

# Создаем асинхронный "движок" и фабрику сессий для работы с БД
try:
    async_engine = create_async_engine(DATABASE_URL)
    async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    logging.info("Соединение с базой данных успешно установлено.")
except Exception as e:
    logging.error(f"Ошибка подключения к базе данных: {e}")

async def init_db():
    """Инициализирует таблицы в базе данных (создает их, если не существуют)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Таблицы в базе данных успешно инициализированы.")

async def get_or_create_user(telegram_id: int, username: str | None) -> User:
    """Находит пользователя по telegram_id или создает нового, если он не найден."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(telegram_id=telegram_id, username=username)
            session.add(user)
            await session.commit()
            logging.info(f"Создан новый пользователь с telegram_id: {telegram_id}")
        
        return user

async def save_user_details(telegram_id: int, data: dict):
    """Универсально сохраняет любые собранные данные пользователя в его JSON-поле."""
    async with async_session_factory() as session:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(user_data=data)
        )
        await session.execute(stmt)
        await session.commit()
    logging.info(f"Данные для пользователя {telegram_id} успешно сохранены в БД.")

# --- НАЧАЛО НОВОГО БЛОКА ---

async def set_onboarding_completed(telegram_id: int, status: bool = True):
    """
    Устанавливает флаг завершения онбординга для пользователя.
    """
    async with async_session_factory() as session:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(onboarding_completed=status)
        )
        await session.execute(stmt)
        await session.commit()
    logging.info(f"Статус онбординга для пользователя {telegram_id} изменен на {status}.")

# --- КОНЕЦ НОВОГО БЛОКА ---

async def save_history(user_id: str, role: str, content: str):
    """Сохраняет одно сообщение в историю диалога."""
    async with async_session_factory() as session:
        user = await get_or_create_user(int(user_id), None)
        if user:
            history_entry = DialogHistory(user_id=user.id, role=role, message=content)
            session.add(history_entry)
            await session.commit()
        else:
            logging.warning(f"Попытка сохранить историю для несуществующего пользователя {user_id}")

async def load_history(user_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """Загружает последние сообщения из истории диалога в формате, понятном для LLM."""
    async with async_session_factory() as session:
        user = await get_or_create_user(int(user_id), None)
        if not user:
            return []
        
        result = await session.execute(
            select(DialogHistory)
            .where(DialogHistory.user_id == user.id)
            .order_by(desc(DialogHistory.created_at))
            .limit(limit)
        )
        history = result.scalars().all()
        return [{"role": msg.role, "content": msg.message} for msg in reversed(history)]
