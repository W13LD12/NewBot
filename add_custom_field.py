from aiogram.fsm.state import StatesGroup, State

class AddCustomField(StatesGroup):
    waiting_for_field_name = State()
    waiting_for_field_type = State()