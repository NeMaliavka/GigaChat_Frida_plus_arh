from aiogram.fsm.state import State, StatesGroup

class SalesFunnel(StatesGroup):
    """Состояния для воронки продаж."""
    # Состояние, в котором бот ожидает ответа о льготной категории
    AwaitingCategory = State()
    # Здесь в будущем можно будет добавлять другие состояния, 
    # например, для записи на урок: AwaitingName, AwaitingPhone и т.д.
