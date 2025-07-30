from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from fsm import FinanceLog
from datetime import datetime

from database import add_finance_entry, get_finance_entries, get_balance, get_categories, add_category

router = Router(name="finance")


# 💰 /деньги — FSM добавления дохода или расхода
@router.message(Command("деньги"))
async def start_money_entry(message: Message, state: FSMContext):
    await message.answer("Это доход или расход?")
    await state.set_state(FinanceLog.entry_type)


@router.message(FinanceLog.entry_type)
async def get_amount(message: Message, state: FSMContext):
    entry_type = message.text.strip().lower()
    if entry_type not in ["доход", "расход"]:
        await message.answer("Введи только 'доход' или 'расход'")
        return

    await state.update_data(entry_type=entry_type)
    await message.answer("Сколько (в рублях)?")
    await state.set_state(FinanceLog.amount)


@router.message(FinanceLog.amount)
async def get_category(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("Введи сумму цифрами")
        return

    await state.update_data(amount=amount)
    await message.answer("Укажи категорию (например: еда, такси):")
    await state.set_state(FinanceLog.category)


@router.message(FinanceLog.category)
async def save_money_entry(message: Message, state: FSMContext):
    category = message.text.strip()
    data = await state.get_data()

    await add_finance_entry(
        user_id=message.from_user.id,
        entry_type=data["entry_type"],
        amount=data["amount"],
        category=category,
        date=datetime.now().strftime("%Y-%m-%d")
    )

    sign = "+" if data["entry_type"] == "доход" else "-"
    await message.answer(f"💰 Записано: {sign}{data['amount']}₽ — {category}")
    await state.clear()


# 📋 /финансы — показать все записи
@router.message(Command("финансы"))
async def show_finances(message: Message):
    entries = await get_finance_entries(message.from_user.id)
    if not entries:
        await message.answer("Нет записей о финансах.")
        return

    text = "💸 Финансовые записи:\n\n"
    for e in entries[-10:]:  # последние 10
        sign = "+" if e["type"] == "доход" else "-"
        text += f"{e['date']}: {sign}{e['amount']}₽ — {e['category']}\n"
    await message.answer(text)


# 💼 /баланс — текущий баланс
@router.message(Command("баланс"))
async def show_balance(message: Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(f"💼 Текущий баланс: {balance:.2f}₽")


# 🏷 /категории — список и добавление
@router.message(Command("категории"))
async def manage_categories(message: Message):
    categories = await get_categories(message.from_user.id)
    text = "🏷 Категории:\n" + ", ".join(categories) + "\n\nДобавить новую: /категория <название>"
    await message.answer(text)


@router.message(F.text.startswith("/категория "))
async def add_new_category(message: Message):
    name = message.text.replace("/категория ", "").strip()
    if not name:
        await message.answer("Укажи название категории после команды")
        return
    await add_category(message.from_user.id, name)
    await message.answer(f"✅ Категория '{name}' добавлена")
