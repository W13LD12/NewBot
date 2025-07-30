from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from datetime import datetime, timedelta

from fsm import AddHabit
from database import save_habits_to_db, delete_habit_from_db, load_habits_from_db
from utils import user_habits

router = Router(name="habit")


# 🫀 /add — запуск FSM для добавления привычки
@router.message(Command("add"))
async def add_cmd(message: Message, state: FSMContext):
    await message.answer("Введи название привычки:")
    await state.set_state(AddHabit.waiting_for_name)


@router.message(AddHabit.waiting_for_name)
async def habit_name_received(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Введи снова:")
        return

    await state.update_data(habit_name=name)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Полезная", callback_data="type_good")],
        [InlineKeyboardButton(text="⚠️ Вредная", callback_data="type_bad")]
    ])
    await message.answer("Это полезная или вредная привычка?", reply_markup=keyboard)
    await state.set_state(AddHabit.waiting_for_type)


@router.callback_query(AddHabit.waiting_for_type)
async def habit_type_received(callback: CallbackQuery, state: FSMContext):
    habit_type = callback.data.split("_")[1]
    await state.update_data(habit_type=habit_type)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✔ Выполнил/не выполнил", callback_data="track_bool")],
        [InlineKeyboardButton(text="🔢 Количество", callback_data="track_qty")]
    ])
    await callback.message.answer("Что отслеживать?", reply_markup=keyboard)
    await state.set_state(AddHabit.waiting_for_tracking)
    await callback.answer()


@router.callback_query(AddHabit.waiting_for_tracking)
async def tracking_type_received(callback: CallbackQuery, state: FSMContext):
    tracking = callback.data.split("_")[1]
    await state.update_data(tracking_type=tracking)
    if tracking == "qty":
        await callback.message.answer("Укажи единицу измерения (например: мл, шт):")
        await state.set_state(AddHabit.waiting_for_unit)
    else:
        await send_deadline_keyboard(callback.message)
        await state.set_state(AddHabit.waiting_for_deadline)
    await callback.answer()


@router.message(AddHabit.waiting_for_unit)
async def unit_received(message: Message, state: FSMContext):
    unit = message.text.strip()
    if not unit:
        await message.answer("Единица измерения не может быть пустой. Введи снова:")
        return
    await state.update_data(unit=unit)
    await send_deadline_keyboard(message)
    await state.set_state(AddHabit.waiting_for_deadline)


async def send_deadline_keyboard(msg: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня +1 час", callback_data="dl_plus1h")],
        [InlineKeyboardButton(text="Сегодня в 20:00", callback_data="dl_20")],
        [InlineKeyboardButton(text="Завтра в 09:00", callback_data="dl_tomorrow")],
        [InlineKeyboardButton(text="Указать вручную", callback_data="dl_manual")]
    ])
    await msg.answer("Выбери дедлайн:", reply_markup=keyboard)


@router.callback_query(AddHabit.waiting_for_deadline)
async def deadline_chosen(callback: CallbackQuery, state: FSMContext):
    now = datetime.now()
    data = callback.data

    if data == "dl_plus1h":
        deadline = now + timedelta(hours=1)
    elif data == "dl_20":
        deadline = now.replace(hour=20, minute=0)
    elif data == "dl_tomorrow":
        deadline = (now + timedelta(days=1)).replace(hour=9, minute=0)
    elif data == "dl_manual":
        await callback.message.answer("Введи дедлайн вручную (ГГГГ-ММ-ДД ЧЧ:ММ):")
        await state.set_state(AddHabit.waiting_for_manual_deadline)
        await callback.answer()
        return
    else:
        await callback.answer("❌ Неизвестный формат дедлайна")
        return

    await state.update_data(deadline=deadline.isoformat())
    await send_repeat_keyboard(callback.message)
    await state.set_state(AddHabit.waiting_for_repeat)
    await callback.answer()


async def send_repeat_keyboard(msg: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Каждый день", callback_data="repeat_daily")],
        [InlineKeyboardButton(text="Каждую неделю", callback_data="repeat_weekly")],
        [InlineKeyboardButton(text="Без повтора", callback_data="repeat_none")]
    ])
    await msg.answer("Установить повтор?", reply_markup=keyboard)


@router.message(AddHabit.waiting_for_manual_deadline)
async def manual_deadline_entered(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        deadline = datetime.strptime(text, "%Y-%m-%d %H:%M")
        await state.update_data(deadline=deadline.isoformat())
        await send_repeat_keyboard(message)
        await state.set_state(AddHabit.waiting_for_repeat)
    except ValueError:
        await message.answer("Неверный формат. Введи так: 2025-08-01 18:30")


@router.callback_query(AddHabit.waiting_for_repeat)
async def repeat_chosen(callback: CallbackQuery, state: FSMContext):
    repeat = callback.data.replace("repeat_", "")
    await state.update_data(repeat=repeat)

    data = await state.get_data()
    user_id = callback.from_user.id

    # 🧾 Сохраняем привычку
    await save_habits_to_db(user_id, data["habit_name"], {
        "habit_type": data["habit_type"],
        "tracking_type": data["tracking_type"],
        "unit": data.get("unit", ""),
        "deadline": data.get("deadline", ""),
        "repeat": data.get("repeat", "")
    })

    user_habits[user_id] = await load_habits_from_db(user_id)
    await callback.message.answer(f"✅ Привычка '{data['habit_name']}' добавлена.")
    await state.clear()
    await callback.answer()


# 🧾 /report — показать текущие привычки
@router.message(Command("report"))
async def report_cmd(message: Message):
    user_id = message.from_user.id
    habits = user_habits.get(user_id, {})

    if not habits:
        await message.answer("У тебя пока нет привычек. Добавь с помощью /add")
        return

    text = "📋 Твои привычки:\n\n"
    for i, (name, h) in enumerate(habits.items(), 1):
        habit_type = "полезная" if h["habit_type"] == "good" else "вредная"
        tracking_type = "кол-во" if h.get("tracking_type") == "qty" else "да/нет"
        unit = f" ({h['unit']})" if h.get("unit") else ""
        text += f"{i}. {name} — {habit_type} / {tracking_type}{unit}\n"

    await message.answer(text)


# ❌ /deletehabit — удалить привычку
@router.message(Command("deletehabit"))
async def delete_habit_start(message: Message):
    user_id = message.from_user.id
    habits = user_habits.get(user_id, {})

    if not habits:
        await message.answer("У тебя нет привычек для удаления.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"delete:{name}")]
            for name in habits
        ]
    )
    await message.answer("Выбери привычку, которую хочешь удалить:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("delete:"))
async def confirm_delete(callback: CallbackQuery):
    user_id = callback.from_user.id
    name = callback.data.split(":")[1]

    await delete_habit_from_db(user_id, name)
    user_habits[user_id] = await load_habits_from_db(user_id)
    await callback.message.edit_text(f"❌ Привычка '{name}' удалена.")
    await callback.answer()