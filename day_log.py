from aiogram.fsm.state import StatesGroup, State

class DayLog(StatesGroup):
    waiting_for_water = State()
    waiting_for_food = State()
    waiting_for_product = State()
    waiting_for_grams = State()
    waiting_for_next_food = State()
    waiting_for_cigarettes = State()
    waiting_for_exercise = State()
    waiting_for_expenses = State()
    waiting_for_income = State()
    waiting_for_mood = State()
    waiting_for_thoughts = State()
    waiting_for_sleep = State()