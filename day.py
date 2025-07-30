from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from fsm import DayLog
from datetime import datetime

from database import get_or_create_daily_log, save_daily_log

router = Router(name="day")


# 📅 /день — FSM лог дня (вода, сиги, активность, настроение, мысли)
@router.message(Command("день"))
async def start_day_log(message: Message, state: FSMContext):
    await message.answer("Сколько воды выпил (в мл)?")
    await state.set_state(DayLog.water)


@router.message(DayLog.water)
async def log_smoke(message: Message, state: FSMContext):
    try:
        water = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число в мл.")
        return
    await state.update_data(water=water)
    await message.answer("Сколько сигарет выкурил?")
    await state.set_state(DayLog.smoke)


@router.message(DayLog.smoke)
async def log_activity(message: Message, state: FSMContext):
    try:
        smoke = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число сигарет.")
        return
    await state.update_data(smoke=smoke)
    await message.answer("Была ли физическая активность? (да/нет)")
    await state.set_state(DayLog.activity)


@router.message(DayLog.activity)
async def log_mood(message: Message, state: FSMContext):
    activity = message.text.strip().lower()
    await state.update_data(activity=activity)
    await message.answer("Как настроение по шкале от 1 до 10?")
    await state.set_state(DayLog.mood)


@router.message(DayLog.mood)
async def log_thoughts(message: Message, state: FSMContext):
    try:
        mood = int(message.text.strip())
        if not (1 <= mood <= 10): raise ValueError
    except ValueError:
        await message.answer("Введи число от 1 до 10.")
        return
    await state.update_data(mood=mood)
    await message.answer("Хочешь оставить мысли за день?")
    await state.set_state(DayLog.thoughts)


@router.message(DayLog.thoughts)
async def finish_day_log(message: Message, state: FSMContext):
    thoughts = message.text.strip()
    data = await state.get_data()

    db_data = await get_or_create_daily_log(message.from_user.id)
    db_data.update({
        "water": data["water"],
        "smoke": data["smoke"],
        "activity": data["activity"],
        "mood": data["mood"],
        "thoughts": thoughts
    })

    await save_daily_log(message.from_user.id, db_data)
    await state.clear()

    await message.answer("✅ Лог за сегодня сохранён. Возвращайся завтра.")


# 🧾 /отчёт — вывести лог за сегодня
@router.message(Command("отчёт"))
async def show_day_log(message: Message):
    data = await get_or_create_daily_log(message.from_user.id)
    if not data:
        await message.answer("Нет данных за сегодня.")
        return

    text = (
        f"🧾 Отчёт за день:\n"
        f"💧 Вода: {data.get('water', 0)} мл\n"
        f"🚬 Сигареты: {data.get('smoke', 0)}\n"
        f"🏃 Активность: {data.get('activity', 'нет')}\n"
        f"🙂 Настроение: {data.get('mood', '-')}\n"
        f"🧠 Мысли: {data.get('thoughts', '—')}"
    )
    await message.answer(text)