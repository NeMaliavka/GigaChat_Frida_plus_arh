from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# Импортируем нашу новую фабрику
from app.keyboards.callbacks import EnrollmentCallback

def get_enroll_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопками, использующими EnrollmentCallback.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="Узнать подробнее о программе",
                # Создаем колбек с действием 'program_details'
                callback_data=EnrollmentCallback(action="program_details").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="Подобрать время для пробного урока",
                # Создаем колбек с действием 'book_trial'
                callback_data=EnrollmentCallback(action="book_trial").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
