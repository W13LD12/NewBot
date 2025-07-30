import logging
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from openpyxl import Workbook

from fsm import AddHabit, DayLog, AddCustomField, FinanceLog
from config import bot, OWNER_ID, GROUP_CHAT_ID
from database import (
    save_custom_field,
    get_nutrition_summary,
    get_product_by_name,
    add_product,
    get_products,
    add_meal,
    update_product,
    get_finance_categories,
    add_finance_operation,
    add_finance_category
)


from utils import user_habits

router = Router()
logger = logging.getLogger(__name__)

# Команда /start — приветствие и загрузка привычек
@router.message(Command('start'))
async def start_handler(message: Message):
    user_id = message.from_user.id
    logger.info(f"✅ Пользователь {user_id} нажал /start")
    user_habits[user_id] = await load_habits_from_db(user_id)

    await message.answer(
        "Привет! Я бот, который помогает тебе отслеживать свою жизнь.\n\n"
        "🧭 Используй /help, чтобы посмотреть все команды."
    )
# Команда /help — список команд
@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(   
        "Вот что я умею:\n\n"
        "📌 Основное:\n"
        "• /add — добавить привычку (полезную или вредную)\n"
        "• /day — заполнить лог дня (вода, еда, сигареты, мысли...)\n"
        "• /report — показать текущие привычки\n"
        "• /export — экспорт в Excel\n"
        "• /deletehabit — удалить привычку\n\n"
        "📅 Логи:\n"
        "• /history — последние 7 записей\n"
        "• /week — отчёт за неделю\n"
        "• /month — отчёт за месяц\n\n"
        "💡 Кастом:\n"
        "• /custom — добавить своё поле в дневник\n"
        "• /delcustom — удалить кастомное поле\n\n"
        "🍎 Продукты:\n"
        "• /products — список продуктов\n"
        "• /delproduct — удалить продукт\n"
        "• /editproduct — редактировать продукт\n\n"
        "💰 Финансы:\n"
        "• /finance — учёт расходов и доходов\n"
        "• /categories — категории финансов\n"
        "• /balance — баланс за неделю\n\n"
        "🔔 Напоминания:\n"
        "• /remind HH:MM — установить напоминание\n"
        "• /remind_off — отключить напоминание"
    )


# Команда /add — запуск FSM для добавления привычки
@router.message(Command("add"))
async def add_cmd(message: Message, state: FSMContext):
    await message.answer("Введи название привычки:")
    await state.set_state(AddHabit.waiting_for_name)
    logger.info(f"[ADD] user={message.from_user.id} начал добавление привычки")

# Шаг 1 — название привычки
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

# Шаг 2 — тип привычки
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

# Шаг 3 — тип отслеживания (да/нет или количество)
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

# Шаг 4 (если количество) — ввод единицы измерения
@router.message(AddHabit.waiting_for_unit)
async def unit_received(message: Message, state: FSMContext):
    unit = message.text.strip()
    if not unit:
        await message.answer("Единица измерения не может быть пустой. Введи снова:")
        return
    await state.update_data(unit=unit)
    await send_deadline_keyboard(message)
    await state.set_state(AddHabit.waiting_for_deadline)

# Вспомогательная функция — клавиатура с дедлайнами
async def send_deadline_keyboard(msg: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня +1 час", callback_data="dl_plus1h")],
        [InlineKeyboardButton(text="Сегодня в 20:00", callback_data="dl_20")],
        [InlineKeyboardButton(text="Завтра в 09:00", callback_data="dl_tomorrow")],
        [InlineKeyboardButton(text="Указать вручную", callback_data="dl_manual")]
    ])
    await msg.answer("Выбери дедлайн:", reply_markup=keyboard)

# Шаг 5 — выбор дедлайна
@router.callback_query(AddHabit.waiting_for_deadline)
async def deadline_chosen(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    now = datetime.now()

    # Конвертация выбранного варианта в дату
    if data == "dl_plus1h":
        deadline = now + timedelta(hours=1)
    elif data == "dl_20":
        deadline = now.replace(hour=20, minute=0, second=0, microsecond=0)
    elif data == "dl_tomorrow":
        deadline = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    elif data == "dl_manual":
        await callback.message.answer("Введи дедлайн вручную (ГГГГ-ММ-ДД ЧЧ:ММ):")
        await state.set_state(AddHabit.waiting_for_manual_deadline)
        await callback.answer()
        return
    else:
        await callback.answer("Неизвестный формат дедлайна")
        return

    await state.update_data(deadline=deadline.isoformat())
    await send_repeat_keyboard(callback.message)
    await state.set_state(AddHabit.waiting_for_repeat)
    await callback.answer()

# Вспомогательная функция — выбор повтора привычки
async def send_repeat_keyboard(msg: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Каждый день", callback_data="repeat_daily")],
        [InlineKeyboardButton(text="Каждую неделю", callback_data="repeat_weekly")],
        [InlineKeyboardButton(text="Без повтора", callback_data="repeat_none")]
    ])
    await msg.answer("Установить повтор?", reply_markup=keyboard)

# Шаг 6 (если ручной ввод дедлайна)
@router.message(AddHabit.waiting_for_manual_deadline)
async def manual_deadline_entered(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        deadline = datetime.strptime(text, "%Y-%m-%d %H:%M")
        await state.update_data(deadline=deadline.isoformat())
        await send_repeat_keyboard(message)
        await state.set_state(AddHabit.waiting_for_repeat)
    except ValueError:
        await message.answer("Неверный формат. Введи в виде: ГГГГ-ММ-ДД ЧЧ:ММ")
# Шаг 7 — выбор повтора привычки
@router.callback_query(AddHabit.waiting_for_repeat)
async def repeat_chosen(callback: CallbackQuery, state: FSMContext):
    # Извлекаем повтор: repeat_daily → daily
    repeat = callback.data.replace("repeat_", "")
    await state.update_data(repeat=repeat)

    data = await state.get_data()
    user_id = callback.from_user.id

    # Получаем все параметры привычки из FSM
    name = data["habit_name"]
    habit_type = data["habit_type"]
    tracking = data["tracking_type"]
    unit = data.get("unit", "")
    deadline = data.get("deadline", "")
    repeat_value = repeat

    # Сохраняем в базу данных
    await save_habits_to_db(user_id, name, {
        "habit_type": habit_type,
        "tracking_type": tracking,
        "unit": unit,
        "deadline": deadline,
        "repeat": repeat_value
    })

    # Обновляем кэш привычек
    user_habits[user_id] = await load_habits_from_db(user_id)

    await callback.message.answer(f"✅ Привычка '{name}' добавлена.")
    await state.clear()
    await callback.answer()

# ===== /report — показать текущие привычки =====
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

# ===== /deletehabit — удаление привычки =====
@router.message(Command("deletehabit"))
async def delete_habit_start(message: Message):
    user_id = message.from_user.id
    habits = user_habits.get(user_id, {})

    if not habits:
        await message.answer("У тебя нет привычек для удаления.")
        return

    # Клавиатура с выбором привычки для удаления
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

    # Удаляем из БД и обновляем кэш
    await delete_habit_from_db(user_id, name)
    user_habits[user_id] = await load_habits_from_db(user_id)

    await callback.message.edit_text(f"❌ Привычка '{name}' удалена.")
    await callback.answer()

# ===== /export — экспорт привычек и логов в Excel =====
@router.message(Command("export"))
async def export_to_excel(message: Message):
    import json
    from database import get_custom_fields

    user_id = message.from_user.id
    habits = user_habits.get(user_id, {})

    # Создаём Excel-файл
    wb = Workbook()
    ws_habits = wb.active
    ws_habits.title = "Привычки"
    ws_habits.append(["Название", "Тип", "Трек", "Единица", "Дедлайн", "Повтор"])

    # Заполняем лист привычек
    for name, h in habits.items():
        ws_habits.append([
            name,
            "Полезная" if h.get("habit_type") == "good" else "Вредная",
            "Да/нет" if h.get("tracking_type") == "bool" else "Количество",
            h.get("unit", ""),
            h.get("deadline", ""),
            h.get("repeat", "")
        ])

    # Получаем кастомные поля для логов
    custom_fields = get_custom_fields(user_id)
    custom_names = [f[0] for f in custom_fields]

    # Создаём лист логов дня
    ws_logs = wb.create_sheet("Логи дня")
    headers = ["Дата", "Вода (мл)", "Сигареты", "Зарядка", "Расходы", "Доход", "Настроение", "Энергия", "Мысли"] + custom_names
    ws_logs.append(headers)

    # Загружаем логи из базы
    with sqlite3.connect("habits.db") as conn:
        rows = conn.execute("""
            SELECT date, water, cigarettes, exercise, expenses, income, mood, energy, thoughts, custom_data
            FROM daily_logs WHERE user_id = ? ORDER BY date DESC
        """, (user_id,)).fetchall()

        for row in rows:
            (
                date, water, cigs, exercise, expenses,
                income, mood, energy, thoughts, custom_json
            ) = row
            try:
                custom_dict = json.loads(custom_json) if custom_json else {}
            except:
                custom_dict = {}

            # Значения по всем кастомным полям
            custom_values = [custom_dict.get(name, "") for name in custom_names]

            ws_logs.append([
                date, water, cigs, exercise, expenses,
                income, mood, energy, thoughts
            ] + custom_values)

    # Сохраняем во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        wb.save(tmp.name)
        path = tmp.name

    # Отправляем пользователю файл
    file_for_user = FSInputFile(path, filename="export.xlsx")
    await message.answer_document(file_for_user)

    # Если отправитель — владелец, дублируем в группу
    if user_id == OWNER_ID:
        file_for_group = FSInputFile(path, filename="export.xlsx")
        await bot.send_document(
            GROUP_CHAT_ID,
            file_for_group,
            caption=f"📊 Экспорт от @{message.from_user.username or user_id}"
        )

    os.remove(path)
    logger.info(f"[EXPORT_DONE] user={user_id} → export.xlsx удалён")


# --- Напоминания ---
@router.message(Command("remind"))
async def save_reminder(message: Message):
    """
    Устанавливает напоминание для пользователя на определённое время.
    Формат команды: /remind HH:MM
    """
    from database import set_reminder
    import re

    user_id = message.from_user.id
    text = message.text.strip()

    # Проверяем формат времени
    match = re.match(r"/remind\s+(\d{1,2}):(\d{2})", text)
    if not match:
        await message.answer("Неверный формат. Введи время в виде /remind 09:00")
        return

    hours, minutes = map(int, match.groups())
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        await message.answer("Время должно быть от 00:00 до 23:59")
        return

    formatted_time = f"{hours:02d}:{minutes:02d}"
    set_reminder(user_id, formatted_time)
    await message.answer(f"🔔 Напоминание установлено на {formatted_time}")

@router.message(Command("remind_off"))
async def turn_off_reminder(message: Message):
    """
    Отключает напоминание для пользователя.
    """
    from database import delete_reminder

    user_id = message.from_user.id
    delete_reminder(user_id)
    await message.answer("🔕 Напоминание отключено")


# --- Кастомные поля ---
@router.message(Command("кастом"))
async def start_custom_field(message: Message, state: FSMContext):
    """
    Запускает процесс добавления кастомного поля для дневника.
    """
    await message.answer("Введи название нового поля:")
    await state.set_state(AddCustomField.waiting_for_name)

@router.message(AddCustomField.waiting_for_name)
async def custom_field_name(message: Message, state: FSMContext):
    """
    Получает название кастомного поля.
    """
    field_name = message.text.strip()
    if not field_name:
        await message.answer("Название не может быть пустым. Введи снова:")
        return
    await state.update_data(field_name=field_name)

    # Клавиатура выбора типа поля
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да/Нет", callback_data="type_bool")],
        [InlineKeyboardButton(text="Число", callback_data="type_int")],
        [InlineKeyboardButton(text="Текст", callback_data="type_text")]
    ])
    await message.answer("Выбери тип поля:", reply_markup=keyboard)
    await state.set_state(AddCustomField.waiting_for_type)

@router.callback_query(F.data.startswith("type_"), AddCustomField.waiting_for_type)
async def custom_field_type(callback: CallbackQuery, state: FSMContext):
    """
    Сохраняет выбранный тип кастомного поля и добавляет его в базу.
    """
    from database import add_custom_field

    field_type = callback.data.split("_")[1]  # type_bool -> bool
    data = await state.get_data()
    field_name = data.get("field_name")

    if not field_name:
        await callback.message.answer("❌ Ошибка: не удалось получить имя поля.")
        return

    add_custom_field(callback.from_user.id, field_name, field_type)
    await callback.message.answer(f"✅ Кастомное поле «{field_name}» ({field_type}) добавлено.")
    await state.clear()
    await callback.answer()

@router.message(Command("delcustom"))
async def delete_custom_field_start(message: Message):
    """
    Запускает процесс удаления кастомного поля.
    """
    from database import get_custom_fields
    user_id = message.from_user.id
    fields = get_custom_fields(user_id)
    if not fields:
        await message.answer("У тебя нет кастомных полей.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"delcustom:{name}")]
            for name, _ in fields
        ]
    )
    await message.answer("Выбери поле, которое хочешь удалить:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("delcustom:"))
async def delete_custom_field_confirm(callback: CallbackQuery):
    """
    Удаляет выбранное кастомное поле из базы.
    """
    from database import delete_custom_field
    user_id = callback.from_user.id
    field_name = callback.data.split(":", 1)[1]

    delete_custom_field(user_id, field_name)
    await callback.message.edit_text(f"❌ Поле '{field_name}' удалено.")
    await callback.answer()


from fsm import CustomFieldInput
import json

@router.message(CustomFieldInput.waiting_for_bool_value)
async def handle_bool_field(message: Message, state: FSMContext):
    """
    Обрабатывает значение кастомного поля типа bool (да/нет).
    """
    answer = message.text.strip().lower()
    if answer not in ["да", "нет"]:
        await message.answer("Ответ должен быть 'да' или 'нет'.")
        return
    value = answer == "да"
    await handle_next_custom_field(message, state, value)

@router.message(CustomFieldInput.waiting_for_int_value)
async def handle_int_field(message: Message, state: FSMContext):
    """
    Обрабатывает значение кастомного поля типа int (целое число).
    """
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введи целое число:")
        return
    await handle_next_custom_field(message, state, value)

@router.message(CustomFieldInput.waiting_for_text_value)
async def handle_text_field(message: Message, state: FSMContext):
    """
    Обрабатывает значение кастомного поля типа text (строка).
    """
    value = message.text.strip()
    await handle_next_custom_field(message, state, value)
async def handle_next_custom_field(message: Message, state: FSMContext, value):
    """
    Переходит к следующему кастомному полю или сохраняет лог дня, если все поля заполнены.
    """
    data = await state.get_data()
    index = data["current_field_index"]
    custom_fields = data["custom_fields"]
    answers = data["custom_answers"]

    field_name, _ = custom_fields[index]
    answers[field_name] = value

    index += 1
    if index >= len(custom_fields):
        # Все поля заполнены — сохраняем лог дня
        await save_full_day_log(message, state, answers)
    else:
        # Переход к следующему полю
        field_name, field_type = custom_fields[index]
        await state.update_data(current_field_index=index, custom_answers=answers)
        if field_type == "bool":
            await message.answer(f"{field_name}? (да/нет)")
            await state.set_state(CustomFieldInput.waiting_for_bool_value)
        elif field_type == "int":
            await message.answer(f"{field_name}? (число)")
            await state.set_state(CustomFieldInput.waiting_for_int_value)
        elif field_type == "text":
            await message.answer(f"{field_name}? (текст)")
            await state.set_state(CustomFieldInput.waiting_for_text_value)



# --- История логов ---
@router.message(Command("history"))
async def history_handler(message: Message):
    """
    Показывает последние 7 записей дневника пользователя.
    """
    import json
    from database import get_custom_fields

    user_id = message.from_user.id
    custom_fields = get_custom_fields(user_id)
    custom_names = [f[0] for f in custom_fields]

    with sqlite3.connect("habits.db") as conn:
        rows = conn.execute("""
            SELECT date, water, cigarettes, exercise, expenses, income, mood, energy, thoughts, custom_data
            FROM daily_logs
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 7
        """, (user_id,)).fetchall()

    if not rows:
        await message.answer("Нет записей за последние дни.")
        return

    response = "🕓 Последние 7 записей:\n"
    for row in rows:
        (
            date, water, cigs, exercise, expenses,
            income, mood, energy, thoughts, custom_json
        ) = row
        response += f"\n📅 <b>{date}</b>\n"
        response += f"💧 Вода: {water} мл\n"

        nutrition = get_nutrition_summary(user_id, date)
        response += (
            f"🍽 Питание:\n"
            f"  • Калории: {nutrition['calories']:.0f} ккал\n"
            f"  • Белки: {nutrition['protein']:.1f} г\n"
            f"  • Жиры: {nutrition['fat']:.1f} г\n"
            f"  • Углеводы: {nutrition['carbs']:.1f} г\n"
            f"  • Соль: {nutrition['salt']:.1f} г\n"
            f"  • Сахар: {nutrition['sugar']:.1f} г\n"
        )

        response += f"🚬 Сигареты: {cigs}\n"
        response += f"🏃 Активность: {exercise}\n"
        response += f"💸 Расходы: {expenses} ₽ | Доход: {income} ₽\n"
        response += f"🙂 Настроение: {mood} / ⚡ Энергия: {energy}\n"
        response += f"🧠 Мысли: {thoughts or '—'}\n"

        try:
            custom_dict = json.loads(custom_json) if custom_json else {}
        except:
            custom_dict = {}

        if custom_dict:
            response += "🔧 Кастом:\n"
            for name in custom_names:
                value = custom_dict.get(name, "—")
                response += f"• {name}: {value}\n"
        response += "─" * 25 + "\n"

    await message.answer(response, parse_mode="HTML")

@router.message(Command("week"))
async def week_handler(message: Message):
    """
    Показывает логи за последние 7 дней.
    """
    import json
    from database import get_custom_fields
    from datetime import datetime, timedelta

    user_id = message.from_user.id
    custom_fields = get_custom_fields(user_id)
    custom_names = [f[0] for f in custom_fields]

    since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    with sqlite3.connect("habits.db") as conn:
        rows = conn.execute("""
            SELECT date, water, cigarettes, exercise, expenses, income, mood, energy, thoughts, custom_data
            FROM daily_logs
            WHERE user_id = ? AND date >= ?
            ORDER BY date DESC
        """, (user_id, since_date)).fetchall()

    if not rows:
        await message.answer("Нет записей за последние 7 дней.")
        return

    response = "🗓️ Лог за последние 7 дней:\n"
    for row in rows:
        (
            date, water, cigs, exercise, expenses,
            income, mood, energy, thoughts, custom_json
        ) = row
        response += f"\n📅 <b>{date}</b>\n"
        response += f"💧 Вода: {water} мл\n"

        nutrition = get_nutrition_summary(user_id, date)
        response += (
            f"🍽 Питание:\n"
            f"  • Калории: {nutrition['calories']:.0f} ккал\n"
            f"  • Белки: {nutrition['protein']:.1f} г\n"
            f"  • Жиры: {nutrition['fat']:.1f} г\n"
            f"  • Углеводы: {nutrition['carbs']:.1f} г\n"
            f"  • Соль: {nutrition['salt']:.1f} г\n"
            f"  • Сахар: {nutrition['sugar']:.1f} г\n"
        )

        response += f"🚬 Сигареты: {cigs}\n"
        response += f"🏃 Активность: {exercise}\n"
        response += f"💸 Расходы: {expenses} ₽ | Доход: {income} ₽\n"
        response += f"🙂 Настроение: {mood} / ⚡ Энергия: {energy}\n"
        response += f"🧠 Мысли: {thoughts or '—'}\n"

        try:
            custom_dict = json.loads(custom_json) if custom_json else {}
        except:
            custom_dict = {}

        if custom_dict:
            response += "🔧 Кастом:\n"
            for name in custom_names:
                value = custom_dict.get(name, "—")
                response += f"• {name}: {value}\n"
        response += "─" * 25 + "\n"

    await message.answer(response, parse_mode="HTML")

@router.message(Command("month"))
async def month_handler(message: Message):
    """
    Показывает логи за текущий месяц.
    """
    import json
    from database import get_custom_fields
    from datetime import datetime

    user_id = message.from_user.id
    custom_fields = get_custom_fields(user_id)
    custom_names = [f[0] for f in custom_fields]

    today = datetime.now()
    month_str = today.strftime("%Y-%m")  # пример: "2025-07"
    with sqlite3.connect("habits.db") as conn:
        rows = conn.execute("""
            SELECT date, water, cigarettes, exercise, expenses, income, mood, energy, thoughts, custom_data
            FROM daily_logs
            WHERE user_id = ? AND date LIKE ?
            ORDER BY date DESC
        """, (user_id, f"{month_str}-%")).fetchall()

    if not rows:
        await message.answer("Нет записей за этот месяц.")
        return

    response = f"📅 Лог за {month_str}:\n"
    for row in rows:
        (
            date, water, cigs, exercise, expenses,
            income, mood, energy, thoughts, custom_json
        ) = row
        response += f"\n📅 <b>{date}</b>\n"
        response += f"💧 Вода: {water} мл\n"

        nutrition = get_nutrition_summary(user_id, date)
        response += (
            f"🍽 Питание:\n"
            f"  • Калории: {nutrition['calories']:.0f} ккал\n"
            f"  • Белки: {nutrition['protein']:.1f} г\n"
            f"  • Жиры: {nutrition['fat']:.1f} г\n"
            f"  • Углеводы: {nutrition['carbs']:.1f} г\n"
            f"  • Соль: {nutrition['salt']:.1f} г\n"
            f"  • Сахар: {nutrition['sugar']:.1f} г\n"
        )

        response += f"🚬 Сигареты: {cigs}\n"
        response += f"🏃 Активность: {exercise}\n"
        response += f"💸 Расходы: {expenses} ₽ | Доход: {income} ₽\n"
        response += f"🙂 Настроение: {mood} / ⚡ Энергия: {energy}\n"
        response += f"🧠 Мысли: {thoughts or '—'}\n"

        try:
            custom_dict = json.loads(custom_json) if custom_json else {}
        except:
            custom_dict = {}

        if custom_dict:
            response += "🔧 Кастом:\n"
            for name in custom_names:
                value = custom_dict.get(name, "—")
                response += f"• {name}: {value}\n"
        response += "─" * 25 + "\n"

    await message.answer(response, parse_mode="HTML")

@router.message(Command("продукты"))
async def show_products(message: Message):
    from database import get_products
    products = get_products()
    if not products:
        await message.answer("База продуктов пуста.")
        return
    text = "🍏 Список продуктов:\n"
    for p in products:
        text += (
            f"• {p[1]} — "
            f"{p[2]} ккал, "
            f"Б:{p[3]} Ж:{p[4]} У:{p[5]} "
            f"Соль:{p[6]} Сахар:{p[7]}\n"
        )
    await message.answer(text)

@router.message(Command("delproduct"))
async def delete_product_start(message: Message):
    from database import get_products
    products = get_products()
    if not products:
        await message.answer("Нет продуктов для удаления.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=p[1], callback_data=f"delprod:{p[0]}")]
            for p in products
        ]
    )
    await message.answer("Выбери продукт для удаления:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("delprod:"))
async def delete_product_confirm(callback: CallbackQuery):
    from database import delete_product
    prod_id = int(callback.data.split(":")[1])
    delete_product(prod_id)
    await callback.message.edit_text("❌ Продукт удалён.")
    await callback.answer()

# --- Редактирование продуктов ---
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_products, update_product

@router.message(Command("editproduct"))
async def edit_product_start(message: Message):
    products = get_products()
    if not products:
        await message.answer("Нет продуктов для редактирования.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=p[1], callback_data=f"editprod:{p[0]}")]
            for p in products
        ]
    )
    await message.answer("Выбери продукт для редактирования:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("editprod:"))
async def edit_product_select(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split(":")[1])
    await state.update_data(prod_id=prod_id)
    await callback.message.edit_text(
        "Введи новые значения через ;\nФормат: калории;белки;жиры;углеводы;соль;сахар"
    )
    await state.set_state("waiting_for_product_edit")

@router.message(F.state == "waiting_for_product_edit")
async def edit_product_save(message: Message, state: FSMContext):
    data = await state.get_data()
    prod_id = data.get("prod_id")
    try:
        parts = message.text.strip().split(";")
        if len(parts) != 6:
            raise ValueError
        calories, protein, fat, carbs, salt, sugar = map(float, parts)
        update_product(prod_id, calories, protein, fat, carbs, salt, sugar)
        await message.answer("✅ Продукт обновлён!")
        await state.clear()
    except Exception:
        await message.answer("Ошибка! Формат: калории;белки;жиры;углеводы;соль;сахар")

# ===== /финансы — учёт финансов =====
@router.message(Command("финансы"))
async def start_finance_log(message: Message, state: FSMContext):
    await message.answer("Что добавить? (расход/доход)")
    await state.set_state(FinanceLog.waiting_for_type)

@router.message(FinanceLog.waiting_for_type)
async def finance_type_received(message: Message, state: FSMContext):
    type_ = message.text.strip().lower()
    if type_ not in ["расход", "доход"]:
        await message.answer("Введи 'расход' или 'доход'.")
        return
    await state.update_data(type=type_)
    user_id = message.from_user.id
    categories = get_finance_categories(user_id, "expense" if type_ == "расход" else "income")
    if categories:
        cat_list = "\n".join([f"{c[0]}. {c[1]}" for c in categories])
        await message.answer(f"Выбери категорию:\n{cat_list}\nИли напиши новую категорию.")
    else:
        await message.answer("Нет категорий. Введи название новой категории.")
    await state.set_state(FinanceLog.waiting_for_category)

@router.message(FinanceLog.waiting_for_category)
async def finance_category_received(message: Message, state: FSMContext):
    cat_text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    type_ = data["type"]
    categories = get_finance_categories(user_id, "expense" if type_ == "расход" else "income")
    cat_id = None
    for c in categories:
        if cat_text == str(c[0]) or cat_text.lower() == c[1].lower():
            cat_id = c[0]
            break
    if not cat_id:
        # Добавляем новую категорию
        add_finance_category(user_id, cat_text, "expense" if type_ == "расход" else "income")
        categories = get_finance_categories(user_id, "expense" if type_ == "расход" else "income")
        cat_id = categories[-1][0]
        await message.answer(f"✅ Категория '{cat_text}' добавлена.")
    await state.update_data(category_id=cat_id)
    await message.answer("Введи сумму (например, 1500):")
    await state.set_state(FinanceLog.waiting_for_amount)

@router.message(FinanceLog.waiting_for_amount)
async def finance_amount_received(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введи сумму числом (например, 1500):")
        return
    data = await state.get_data()
    user_id = message.from_user.id
    date = datetime.now().strftime("%Y-%m-%d")
    add_finance_operation(user_id, date, data["category_id"], amount, "expense" if data["type"] == "расход" else "income")
    await message.answer(f"✅ {data['type'].capitalize()} добавлен: {amount} ₽")
    await state.clear()

@router.message(Command("категории"))
async def show_finance_categories(message: Message):
    user_id = message.from_user.id
    expenses = get_finance_categories(user_id, "expense")
    incomes = get_finance_categories(user_id, "income")
    text = "💸 Категории расходов:\n"
    text += "\n".join([f"• {c[1]}" for c in expenses]) or "—"
    text += "\n\n💰 Категории доходов:\n"
    text += "\n".join([f"• {c[1]}" for c in incomes]) or "—"
    await message.answer(text)

@router.message(Command("баланс"))
async def finance_report(message: Message):
    from database import get_finance_operations
    user_id = message.from_user.id
    today = datetime.now()
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")
    ops = get_finance_operations(user_id, week_ago, today_str)

    if not ops:
        await message.answer("Нет финансовых записей за последние 7 дней.")
        return

    expenses = sum(op[2] for op in ops if op[4] == "expense")
    incomes = sum(op[2] for op in ops if op[4] == "income")
    text = (
        f"💸 Расходы за неделю: {expenses:.2f} ₽\n"
        f"💰 Доходы за неделю: {incomes:.2f} ₽\n"
        f"📊 Баланс: {incomes - expenses:.2f} ₽"
    )
    await message.answer(text)
    from utils import last_activity_time
from datetime import datetime

@router.message()
async def handle_any_message(message: Message):
    global last_activity_time
    last_activity_time = datetime.now()
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()

@router.message(F.text.lower() == "/cancel")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Ввод отменён. Ты свободен.")
# ===== cancel_handler.py =====
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router(name="cancel")

@router.message(F.text.lower() == "/cancel")
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state is None:
        await message.answer("❌ Сейчас нет активного ввода.")
    else:
        await state.clear()
        await message.answer("🚫 Ввод отменён. Ты вышел из режима ввода.")
