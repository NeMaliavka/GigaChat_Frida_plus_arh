# app/db/database.py

import logging
from datetime import datetime
from typing import List, Dict

from sqlalchemy import update, select, delete, func, desc, asc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from .models import Base, User, DialogHistory, TrialLesson, TrialLessonStatus

# --- Инициализация ---
DATABASE_URL = "sqlite+aiosqlite:///app/db/local_database.db"
async_engine = create_async_engine(DATABASE_URL)
async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

async def init_db():
    """Инициализирует базу данных: создает файл и все необходимые таблицы."""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logging.info("Соединение с базой данных успешно установлено и таблицы проверены/созданы.")
    except SQLAlchemyError as e:
        logging.error(f"Критическая ошибка SQLAlchemy при инициализации базы данных: {e}", exc_info=True)
        raise

# --- Функции для работы с пользователем ---

async def get_or_create_user(telegram_id: int, username: str | None) -> User:
    """Находит пользователя по telegram_id или создает нового, если он не найден."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id, username=username)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logging.info(f"Создан новый пользователь с telegram_id: {telegram_id}")
        return user

async def save_user_details(telegram_id: int, data: dict):
    """Универсально сохраняет любые собранные данные пользователя в его JSON-поле."""
    async with async_session_factory() as session:
        stmt = update(User).where(User.telegram_id == telegram_id).values(user_data=data)
        await session.execute(stmt)
        await session.commit()
        logging.info(f"Данные для пользователя {telegram_id} успешно сохранены в БД.")

async def set_onboarding_completed(telegram_id: int, status: bool = True):
    """Устанавливает флаг завершения онбординга для пользователя."""
    async with async_session_factory() as session:
        stmt = update(User).where(User.telegram_id == telegram_id).values(onboarding_completed=status)
        await session.execute(stmt)
        await session.commit()
        logging.info(f"Статус онбординга для пользователя {telegram_id} изменен на {status}.")

# --- Функции для истории диалога ---

async def save_history(user_id: int, role: str, content: str):
    """Сохраняет одно сообщение в историю диалога."""
    async with async_session_factory() as session:
        history_entry = DialogHistory(user_id=user_id, role=role, message=content)
        session.add(history_entry)
        await session.commit()

async def load_history(user_id: int, limit: int = 10) -> List[Dict[str, str]]:
    """Загружает последние сообщения из истории диалога в формате, понятном для LLM."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(DialogHistory)
            .where(DialogHistory.user_id == user_id)
            .order_by(desc(DialogHistory.created_at))
            .limit(limit)
        )
        history = result.scalars().all()
        return [{"role": msg.role, "content": msg.message} for msg in reversed(history)]

# --- Функции для пробных уроков ---

async def add_trial_lesson(user_id: int, task_id: int, event_id: int, teacher_id: int, scheduled_at: datetime):
    """Сохраняет информацию о новой записи на пробный урок."""
    async with async_session_factory() as session:
        new_lesson = TrialLesson(
            user_id=user_id,
            task_id=task_id,
            event_id=event_id,
            teacher_id=teacher_id,
            scheduled_at=scheduled_at,
            status=TrialLessonStatus.PLANNED
        )
        session.add(new_lesson)
        await session.commit()
        logging.info(f"В БД сохранена запись на урок для user_id={user_id} с task_id={task_id}")


async def update_trial_lesson_time(lesson_id: int, new_scheduled_at: datetime):
    """
    Обновляет время и дату запланированного урока после переноса.
    """
    async with async_session_factory() as session:
        try:
            stmt = (
                update(TrialLesson)
                .where(TrialLesson.id == lesson_id)
                .values(scheduled_at=new_scheduled_at)
            )
            await session.execute(stmt)
            await session.commit()
            logging.info(f"Время урока с ID {lesson_id} успешно обновлено на {new_scheduled_at}.")
        except SQLAlchemyError as e:
            logging.error(f"Ошибка БД при обновлении времени урока {lesson_id}: {e}")
            await session.rollback()

            
async def get_active_lesson(user_id: int) -> TrialLesson | None:
    """Находит ближайший будущий запланированный урок."""
    async with async_session_factory() as session:
        stmt = (
            select(TrialLesson)
            .where(
                TrialLesson.user_id == user_id,
                TrialLesson.status == TrialLessonStatus.PLANNED,
                TrialLesson.scheduled_at >= datetime.now()
            )
            .order_by(asc(TrialLesson.scheduled_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

async def cancel_lesson_db(lesson_id: int):
    """Меняет статус урока на 'CANCELLED' в базе данных."""
    async with async_session_factory() as session:
        stmt = update(TrialLesson).where(TrialLesson.id == lesson_id).values(status=TrialLessonStatus.CANCELLED)
        await session.execute(stmt)
        await session.commit()
        logging.info(f"Статус урока с ID {lesson_id} изменен на 'Отменен'.")

# --- Функции для модерации и статистики ---

async def increment_irrelevant_count(user_id: int) -> int:
    """Увеличивает счетчик нерелевантных запросов пользователя на 1."""
    async with async_session_factory() as session:
        user = await session.get(User, user_id)
        if not user: return 0
        user.irrelevant_count = (user.irrelevant_count or 0) + 1
        new_count = user.irrelevant_count
        await session.commit()
        return new_count

async def block_user(user_id: int):
    """Устанавливает флаг is_blocked = True для пользователя."""
    async with async_session_factory() as session:
        stmt = update(User).where(User.id == user_id).values(is_blocked=True)
        await session.execute(stmt)
        await session.commit()
        logging.info(f"Пользователь с ID {user_id} был заблокирован.")

async def unblock_and_reset_user(telegram_id: int) -> bool:
    """Снимает блокировку с пользователя и сбрасывает счетчик."""
    async with async_session_factory() as session:
        stmt = update(User).where(User.telegram_id == telegram_id).values(is_blocked=False, irrelevant_count=0)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

async def get_enrolled_student_count() -> int:
    """Подсчитывает количество пользователей, зачисленных на курс."""
    async with async_session_factory() as session:
        query = select(func.count(User.id)).where(User.is_enrolled == True)
        result = await session.execute(query)
        return result.scalar_one_or_none() or 0
