import logging
from aiogram import Bot
from typing import List, Dict
from app.config import ADMIN_ID

# --- 1. Уведомление о КРИТИЧЕСКОЙ ОШИБКЕ в сценарии ---
# Наша новая функция, которую мы добавили

async def notify_admin_on_error(
    bot: Bot,
    user_id: int,
    username: str | None,
    error_description: str,
    history: List[Dict[str, str]]
):
    """
    Отправляет администратору форматированное уведомление
    о критической ошибке в FSM-сценарии.
    """
    if not ADMIN_ID:
        logging.warning("ADMIN_ID не найден. Уведомление об ошибке не отправлено.")
        return

    # Форматируем историю диалога для наглядности, используя HTML
    history_text = "\n".join([f"<b>{msg['role']}:</b> {msg['content']}" for msg in history])

    text = (
        f"🚨 <b>Критическая ошибка в сценарии!</b> 🚨\n\n"
        f"<b>Пользователь:</b> <a href='tg://user?id={user_id}'>{username or user_id}</a>\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Проблема:</b> {error_description}\n\n"
        f"<b>Последние сообщения:</b>\n{history_text}\n\n"
        f"<i>Требуется немедленное вмешательство!</i>"
    )

    try:
        # Используем parse_mode="HTML" для поддержки ссылок и жирного текста
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        logging.info(f"Администратор уведомлен об ошибке в сценарии для пользователя {user_id}.")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление администратору: {e}")


# --- 2. Уведомление о ПОДОЗРИТЕЛЬНОЙ АКТИВНОСТИ ---
# Ваша существующая функция, немного улучшенная

async def notify_admin_on_suspicious_activity(
    bot: Bot,
    user_id: int,
    username: str | None,
    history: List[Dict[str, str]]
):
    """
    Форматирует и отправляет сообщение администратору о подозрительной активности
    (например, 3 нерелевантных запроса подряд).
    """
    if not ADMIN_ID:
        logging.warning("ADMIN_ID не указан в конфиге. Оповещение не будет отправлено.")
        return

    # Форматируем историю диалога для наглядности, используя HTML
    history_text = "\n".join([f"<b>{msg['role']}:</b> {msg['content']}" for msg in history])
    
    text = (
        f"🕵️‍♂️ <b>Обнаружена подозрительная активность!</b> 🕵️‍♂️\n\n"
        f"<b>Пользователь:</b> <a href='tg://user?id={user_id}'>{username or user_id}</a>\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Причина:</b> Совершил 3 или более нерелевантных запроса подряд.\n\n"
        f"<b>Последние сообщения:</b>\n{history_text}\n\n"
        f"<i>Бот прекратил отвечать этому пользователю для экономии токенов.</i>"
    )
    
    try:
        # Используем parse_mode="HTML" для более красивого и функционального сообщения
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="HTML")
        logging.info(f"Администратору {ADMIN_ID} отправлено оповещение о подозрительной активности по пользователю {user_id}.")
    except Exception as e:
        logging.error(f"Не удалось отправить оповещение администратору: {e}")
