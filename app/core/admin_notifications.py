# app/core/admin_notifications.py

import logging
from typing import List, Dict
from aiogram import Bot
from aiogram.types import User

# Импортируем список ID администраторов из конфига
from app.config import ADMIN_IDS 


async def _send_to_admins(bot: Bot, text: str):
    """
    Вспомогательная функция для безопасной отправки сообщения всем администраторам из списка.
    """
    if not ADMIN_IDS:
        logging.warning("Переменная ADMIN_IDS пуста или не задана. Уведомления не будут отправлены.")
        return

    # Проходим по каждому ID в списке и отправляем сообщение
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as e:
            # Если отправка одному из админов не удалась, логируем ошибку и продолжаем
            logging.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")


# --- 1. Уведомление о запросе пользователя ---
async def notify_admin_of_request(bot: Bot, user: User, request_text: str):
    """
    Отправляет уведомление администратору, когда пользователь просит позвать человека.
    """
    text = (
        f"🙋‍♂️ **Пользователь просит позвать менеджера!**\n\n"
        f"<b>Пользователь:</b> <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Текст запроса:</b> «{request_text}»\n\n"
        f"<i>Пожалуйста, свяжитесь с ним в ближайшее время.</i>"
    )
    await _send_to_admins(bot, text)


# --- 2. Уведомление о блокировке пользователя ---
async def notify_admin_of_block(bot: Bot, user: User, reason: str, history: List[Dict[str, str]]):
    """
    Отправляет уведомление администратору о блокировке пользователя.
    """
    # Берем последние 5 сообщений для контекста
    history_text = "\n".join([f"<b>{msg['role']}:</b> {msg['content']}" for msg in history[-5:]]) 

    text = (
        f"🚫 **Пользователь заблокирован!** 🚫\n\n"
        f"<b>Пользователь:</b> <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Причина:</b> {reason}\n\n"
        f"<b>Последние сообщения:</b>\n{history_text}\n\n"
        f"<i>Для разблокировки используйте команду:</i> `/unblock {user.id}`"
    )
    await _send_to_admins(bot, text)


# --- 3. Уведомление о критической ошибке в коде ---
async def notify_admin_on_error(
    bot: Bot,
    user_id: int,
    username: str | None,
    error_description: str,
    history: List[Dict[str, str]]
):
    """
    Отправляет администратору форматированное уведомление о критической ошибке.
    """
    history_text = "\n".join([f"<b>{msg['role']}:</b> {msg['content']}" for msg in history[-5:]])

    text = (
        f"🚨 <b>Критическая ошибка в работе бота!</b> 🚨\n\n"
        f"<b>Пользователь:</b> <a href='tg://user?id={user_id}'>{username or 'N/A'}</a>\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Описание ошибки:</b> {error_description}\n\n"
        f"<b>Последние сообщения:</b>\n{history_text}\n\n"
        f"<i>Требуется проверка логов и вмешательство разработчика!</i>"
    )
    await _send_to_admins(bot, text)
