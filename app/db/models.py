from sqlalchemy import (
    BigInteger, String, Text, func, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List
from sqlalchemy import Boolean
from sqlalchemy import Integer, Enum
import enum

class Base(DeclarativeBase):
    pass

class User(Base):
    """
    Модель для хранения информации о пользователе.
    Включает универсальное поле `user_data` для хранения любых данных,
    собранных в FSM-сценариях (имена, возраст, марка авто и т.д.).
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    
    # Универсальное поле для хранения любых данных сценария
    user_data: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Связь с историей диалога (один пользователь - много сообщений)
    dialog_history: Mapped[List["DialogHistory"]] = relationship(back_populates="user")

    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Флаг, показывающий, заблокирован ли пользователь
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Счетчик нерелевантных запросов
    irrelevant_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"

class DialogHistory(Base):
    """Модель для хранения истории переписки с каждым пользователем."""
    __tablename__ = 'dialog_history'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    # Определяем роль: 'user' или 'assistant'
    role: Mapped[str] = mapped_column(String(10), nullable=False) 
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    # Связь с пользователем (много сообщений - один пользователь)
    user: Mapped["User"] = relationship(back_populates="dialog_history")

    def __repr__(self):
        return f"<DialogHistory(id={self.id}, role='{self.role}')>"


class TrialLessonStatus(enum.Enum):
    PLANNED = "запланирован"
    COMPLETED = "проведен"
    CANCELLED = "отменен"

class TrialLesson(Base):
    """Модель для отслеживания статуса пробного урока."""
    __tablename__ = 'trial_lessons'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)    
    # ID сущностей из Битрикс24
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    event_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    # ID преподавателя, ответственного за урок. Необходимо для переноса.
    teacher_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    scheduled_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    status: Mapped[TrialLessonStatus] = mapped_column(
        Enum(TrialLessonStatus),
        default=TrialLessonStatus.PLANNED,
        nullable=False
    )


    user: Mapped["User"] = relationship()

    def __repr__(self):
        return f"<TrialLesson(id={self.id}, user_id={self.user_id}, task_id={self.task_id}, status='{self.status.value}')>"
class Feedback(Base):
    """Модель для хранения обратной связи после пробного урока."""
    __tablename__ = 'feedback'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey('trial_lessons.id'), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=True) # Оценка, например, от 1 до 5
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    
    user: Mapped["User"] = relationship()
    lesson: Mapped["TrialLesson"] = relationship()

    def __repr__(self):
        return f"<Feedback(id={self.id}, user_id={self.user_id}, rating={self.rating})>"