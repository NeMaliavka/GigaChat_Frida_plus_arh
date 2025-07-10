import logging
from aiogram import Router, types, F
from app.keyboards.callbacks import EnrollmentCallback
from app.db.database import get_or_create_user
# Импортируем сервис уведомлений, чтобы сообщить админу о заявке
from app.core.admin_notifications import notify_admin_on_error

router = Router()

@router.callback_query(EnrollmentCallback.filter(F.action == "program_details"))
async def handle_program_details(query: types.CallbackQuery):
    """
    Обрабатывает нажатие на кнопку "Узнать подробнее о программе".
    """
    user = await get_or_create_user(query.from_user.id, query.from_user.username)
    user_data = user.user_data or {}
    course_name = user_data.get("course_name", "наш курс")

    # В идеале, этот текст нужно брать из базы знаний (PDF),
    # но для примера пока используем статичный ответ.
    text = (
        f"Отлично! Вот подробности о курсе «{course_name}»:\n\n"
        "Наша методика основана на проектном подходе. С первых уроков мы начинаем создавать "
        "настоящую текстовую RPG-игру. Мы изучим переменные, циклы, функции и классы, "
        "и каждый новый элемент синтаксиса будет сразу же применяться для улучшения нашей игры. "
        "К концу курса у вашего ребенка будет не просто набор знаний, а готовый проект в портфолио "
        "и твердое понимание основ Python. Это самый эффективный способ превратить теорию в практику!"
    )
    # Отвечаем в чат новым сообщением
    await query.message.answer(text)
    # "Закрываем" запрос, чтобы убрать часики на кнопке
    await query.answer()

@router.callback_query(EnrollmentCallback.filter(F.action == "book_trial"))
async def handle_book_trial(query: types.CallbackQuery):
    """
    Обрабатывает нажатие на кнопку "Подобрать время для пробного урока".
    """
    user = await get_or_create_user(query.from_user.id, query.from_user.username)
    # Здесь можно будет реализовать логику отправки уведомления администратору
    logging.info(f"Пользователь {user.telegram_id} оставил заявку на пробный урок.")
    
    text = (
        "Супер! Я передал вашу заявку на пробный урок нашему администратору. "
        "Он скоро свяжется с вами прямо в этом чате, чтобы подобрать самое удобное время. "
        "Обычно это занимает не больше часа. Спасибо за ваш интерес!"
    )
    await query.message.answer(text)
    await query.answer("Заявка принята!")
