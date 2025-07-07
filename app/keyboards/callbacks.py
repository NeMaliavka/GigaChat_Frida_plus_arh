from aiogram.filters.callback_data import CallbackData

class EnrollmentCallback(CallbackData, prefix="enroll"):
    """
    Фабрика для колбеков, связанных с финальным предложением.
    'action' будет хранить действие: 'program_details' или 'book_trial'.
    """
    action: str
