# app/handlers/admin_handlers.py

import logging
from aiogram import Router, types, F
from aiogram.filters import Command

from app.filters.admin_filter import IsAdmin 
from app.db.database import unblock_and_reset_user

# Создаем новый роутер специально для админских команд
router = Router()

# Применяем фильтр ко ВСЕМ обработчикам в этом роутере.
# Это гарантирует, что только администраторы смогут вызывать эти команды.
router.message.filter(IsAdmin())


@router.callback_query(F.data.startswith("admin_unblock_tg:"))
async def unblock_user_command(callback: types.CallbackQuery):
    """
    Обрабатывает нажатие на кнопку 'Разблокировать пользователя' в админском уведомлении.
    """
    try:
        # Извлекаем ID пользователя из callback_data (формат "admin_unblock_tg:USER_ID")
        user_id_to_unblock = int(callback.data.split(":")[1])

        # Вызываем функцию для разблокировки в базе данных
        success = await unblock_and_reset_user(user_id_to_unblock)

        if success:
            # Если всё прошло успешно, редактируем исходное сообщение
            new_text = callback.message.text + "\n\n✅ **Пользователь успешно разблокирован.**"
            await callback.message.edit_text(new_text)
            
            # (Опционально) Уведомляем самого пользователя о том, что он разблокирован
            try:
                await callback.bot.send_message(
                    chat_id=user_id_to_unblock,
                    text="Хорошие новости! Менеджер рассмотрел вашу ситуацию, и блокировка была снята. Можете продолжать общение."
                )
            except Exception as e:
                logging.warning(f"Не удалось уведомить пользователя {user_id_to_unblock} о разблокировке: {e}")
        else:
            # Если по какой-то причине пользователя не нашли в БД
            await callback.message.edit_text(callback.message.text + "\n\n⚠️ **Не удалось найти пользователя в базе данных.**")

    except (IndexError, ValueError) as e:
        # На случай, если callback_data придет в неверном формате
        logging.error(f"Ошибка парсинга user_id из callback_data: {callback.data}. Ошибка: {e}")
        await callback.message.edit_text(callback.message.text + "\n\n❌ **Произошла ошибка при обработке команды.**")
    
    # Отвечаем на колбэк, чтобы убрать "часики" на кнопке
    await callback.answer()
# @router.message(Command(commands=["unblock"]))
# async def unblock_user_command(message: types.Message):
    # """
    # Команда для разблокировки пользователя и сброса его счетчика нерелевантных запросов.
    # Пример использования: /unblock 123456789
    # """
    # try:
    #     # Извлекаем ID пользователя из текста сообщения (второе слово после /unblock)
    #     user_id_to_unblock = int(message.text.split()[1])
    # except (IndexError, ValueError):
    #     await message.answer(
    #         "Неверный формат команды. Используйте: `/unblock ID_пользователя`\n\n"
    #         "ID можно найти в уведомлении о блокировке."
    #     )
    #     return

    # # Вызываем функцию из базы данных для разблокировки
    # if await unblock_and_reset_user(user_id_to_unblock):
    #     logging.info(f"Администратор {message.from_user.id} разблокировал пользователя {user_id_to_unblock}")
    #     await message.answer(f"✅ Пользователь с ID `{user_id_to_unblock}` успешно разблокирован. Счетчик сброшен.")
        
    #     # Пытаемся уведомить пользователя, что его разблокировали
    #     try:
    #         await message.bot.send_message(
    #             user_id_to_unblock,
    #             "Здравствуйте! Менеджер рассмотрел вашу ситуацию, и блокировка с вас снята. Вы снова можете задавать мне вопросы."
    #         )
    #     except Exception as e:
    #         # Если пользователь заблокировал бота, мы не сможем ему написать. Это не критично.
    #         logging.warning(f"Не удалось уведомить пользователя {user_id_to_unblock} о разблокировке: {e}")
    # else:
    #     # Если unblock_and_reset_user вернула False
    #     await message.answer(f"❌ Не удалось найти пользователя с ID `{user_id_to_unblock}` в базе данных.")
    
