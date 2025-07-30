from aiogram.fsm.state import StatesGroup, State

class AddHabit(StatesGroup):
    waiting_for_name = State()
    waiting_for_type = State()
    waiting_for_unit = State()
    waiting_for_repeat = State()
