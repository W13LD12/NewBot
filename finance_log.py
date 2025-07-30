from aiogram.fsm.state import StatesGroup, State

class FinanceLog(StatesGroup):
    waiting_for_date = State()
    waiting_for_type = State()
    waiting_for_category = State()
    waiting_for_sum = State()
