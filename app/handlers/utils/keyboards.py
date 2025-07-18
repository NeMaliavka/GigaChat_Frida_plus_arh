# app/handlers/utils/keyboards.py

from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_existing_user_menu(active_lessons_count: int):
    """Возвращает меню для зарегистрированного пользователя."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Записать ребенка на пробный урок", callback_data="start_booking")
    if active_lessons_count > 0:
        builder.button(text=f"🗓️ Мои записи ({active_lessons_count})", callback_data="check_booking")
        builder.button(text="↪️ Перенести занятие", callback_data="reschedule_booking")
    builder.button(text="💬 Частые вопросы (FAQ)", callback_data="faq_menu")
    builder.button(text="📞 Позвать менеджера", callback_data="human_operator")
    builder.adjust(1)
    return builder.as_markup()

def get_faq_menu():
    """Возвращает меню с частыми вопросами."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Узнать цены", callback_data="faq_price_request")
    builder.button(text="📚 О программе курса", callback_data="faq_course_details")
    builder.button(text="🏫 В чем разница между курсами?", callback_data="faq_course_difference")
    builder.button(text="⬅️ Назад в главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()
