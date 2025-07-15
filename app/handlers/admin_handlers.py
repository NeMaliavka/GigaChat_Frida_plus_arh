# app/handlers/admin_handlers.py

import logging
from aiogram import Router, types
from aiogram.filters import Command

# Предполагается, что у вас есть фильтр для проверки, является ли пользователь админом.
# Если его нет, я покажу, как его создать в Шаге 3.
from app.filters.admin_filter import IsAdmin 
from app.db.database import unblock_and_reset_user

# Создаем новый роутер специально для админских команд
router = Router()

# Применяем фильтр ко ВСЕМ обработчикам в этом роутере.
# Это гарантирует, что только администраторы смогут вызывать эти команды.
router.message.filter(IsAdmin())


@router.message(Command(commands=["unblock"]))
async def unblock_user_command(message: types.Message):
    """
    Команда для разблокировки пользователя и сброса его счетчика нерелевантных запросов.
    Пример использования: /unblock 123456789
    """
    try:
        # Извлекаем ID пользователя из текста сообщения (второе слово после /unblock)
        user_id_to_unblock = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer(
            "Неверный формат команды. Используйте: `/unblock ID_пользователя`\n\n"
            "ID можно найти в уведомлении о блокировке."
        )
        return

    # Вызываем функцию из базы данных для разблокировки
    if await unblock_and_reset_user(user_id_to_unblock):
        logging.info(f"Администратор {message.from_user.id} разблокировал пользователя {user_id_to_unblock}")
        await message.answer(f"✅ Пользователь с ID `{user_id_to_unblock}` успешно разблокирован. Счетчик сброшен.")
        
        # Пытаемся уведомить пользователя, что его разблокировали
        try:
            await message.bot.send_message(
                user_id_to_unblock,
                "Здравствуйте! Менеджер рассмотрел вашу ситуацию, и блокировка с вас снята. Вы снова можете задавать мне вопросы."
            )
        except Exception as e:
            # Если пользователь заблокировал бота, мы не сможем ему написать. Это не критично.
            logging.warning(f"Не удалось уведомить пользователя {user_id_to_unblock} о разблокировке: {e}")
    else:
        # Если unblock_and_reset_user вернула False
        await message.answer(f"❌ Не удалось найти пользователя с ID `{user_id_to_unblock}` в базе данных.")

