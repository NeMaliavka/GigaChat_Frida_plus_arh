# app/db/models.py

import enum
from datetime import datetime
from sqlalchemy import (
    BigInteger, String, ForeignKey, DateTime, func, JSON, Enum, Boolean, Integer, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, declarative_base
from typing import List

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(100))
    # Здесь хранится ЕДИНСТВЕННАЯ актуальная анкета пользователя
    user_data: Mapped[dict | None] = mapped_column(JSON)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enrolled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    irrelevant_count: Mapped[int] = mapped_column(Integer, default=0)
    trial_lessons: Mapped[List["TrialLesson"]] = relationship(back_populates="user")
    dialog_history: Mapped[List["DialogHistory"]] = relationship(back_populates="user")

class DialogHistory(Base):
    __tablename__ = 'dialog_history'
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    role: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user: Mapped["User"] = relationship(back_populates="dialog_history")

class TrialLessonStatus(enum.Enum):
    PLANNED = "запланирован"
    COMPLETED = "проведен"
    CANCELLED = "отменен"

class TrialLesson(Base):
    __tablename__ = 'trial_lessons'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    task_id: Mapped[int | None] = mapped_column(BigInteger)
    event_id: Mapped[int | None] = mapped_column(BigInteger)
    teacher_id: Mapped[int | None] = mapped_column(BigInteger)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[TrialLessonStatus] = mapped_column(
        Enum(TrialLessonStatus), default=TrialLessonStatus.PLANNED
    )
    # Поле lesson_data убрано для простоты и надежности
    user: Mapped["User"] = relationship(back_populates="trial_lessons")

class Feedback(Base):
    __tablename__ = 'feedback'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    lesson_id: Mapped[int] = mapped_column(ForeignKey('trial_lessons.id'))
    rating: Mapped[int | None]
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user: Mapped["User"] = relationship()
    lesson: Mapped["TrialLesson"] = relationship()
