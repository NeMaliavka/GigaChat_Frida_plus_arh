# app/states/fsm_states.py
from aiogram.fsm.state import State, StatesGroup

class GenericFSM(StatesGroup):
    """
    Основной FSM для сценария онбординга.
    """
    InProgress = State()

class WaitlistFSM(StatesGroup):
    """
    FSM для добавления пользователя в лист ожидания.
    """
    waiting_for_contact = State()

class BookingFSM(StatesGroup):
    """
    FSM для процесса бронирования урока.
    """
    choosing_date = State()
    choosing_time = State()
