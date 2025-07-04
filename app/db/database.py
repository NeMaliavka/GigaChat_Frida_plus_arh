import aiosqlite
import logging
from datetime import datetime, timezone
from typing import List, Dict

from app.config import DB_PATH

async def init_db() -> None:
    """Инициализирует таблицы в базе данных, если они не существуют."""
    try:
        # Убедимся, что директория для БД существует
        import os
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    ts TIMESTAMP NOT NULL
                );
            """)
            # Здесь в будущем можно будет добавить таблицы для пользователей,
            # записей на пробные уроки и отзывов.
            await db.commit()
        logging.info("База данных успешно инициализирована.")
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}", exc_info=True)


async def save_history(user_id: str, role: str, text: str) -> None:
    """Сохраняет одно сообщение в историю чата."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO chat_history (user_id, role, message, ts) VALUES (?, ?, ?, ?)",
                (user_id, role, text, datetime.now(timezone.utc))
            )
            await db.commit()
    except Exception as e:
        logging.error(f"Ошибка при сохранении истории для user_id {user_id}: {e}", exc_info=True)


async def load_history(user_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    Загружает последние `limit` сообщений пользователя из истории.
    Это ключевая функция для оптимизации расхода токенов.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                # Запрос выбирает только последние N сообщений, где N=limit
                "SELECT role, message FROM chat_history WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                # Возвращаем сообщения в хронологическом порядке для правильного контекста
                return [{"role": row["role"], "content": row["message"]} for row in reversed(rows)]
    except Exception as e:
        logging.error(f"Ошибка при загрузке истории для user_id {user_id}: {e}", exc_info=True)
        return []

