from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from fsm import DayLog
from datetime import datetime

from database import get_or_create_daily_log, save_daily_log, load_products_from_db, save_product_to_db, delete_product_from_db, update_product_in_db

router = Router(name="food")


# 🍽 /еда — ввести приём пищи и выбрать продукт
@router.message(Command("еда"))
async def start_food_log(message: Message, state: FSMContext):
    await message.answer("Какой приём пищи ты хочешь добавить? (например: завтрак, обед, ужин):")
    await state.set_state(DayLog.food_type)


@router.message(DayLog.food_type)
async def ask_product_name(message: Message, state: FSMContext):
    await state.update_data(food_type=message.text.strip())
    await message.answer("Введи название продукта:")
    await state.set_state(DayLog.product_name)


@router.message(DayLog.product_name)
async def ask_grams(message: Message, state: FSMContext):
    await state.update_data(product_name=message.text.strip())
    await message.answer("Сколько грамм?")
    await state.set_state(DayLog.grams)


@router.message(DayLog.grams)
async def finish_food_log(message: Message, state: FSMContext):
    try:
        grams = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число в граммах.")
        return

    data = await state.get_data()
    product = data.get("product_name")
    food_type = data.get("food_type")

    db_data = await get_or_create_daily_log(message.from_user.id)
    date = datetime.now().strftime("%Y-%m-%d")

    food_entry = {
        "type": food_type,
        "product": product,
        "grams": grams
    }

    db_data.setdefault("food", []).append(food_entry)
    await save_daily_log(message.from_user.id, db_data)

    await message.answer(f"🍽 Добавлено: {food_type} — {product} ({grams}г)")
    await state.clear()


# 📋 /продукты — список всех продуктов
@router.message(Command("продукты"))
async def list_products(message: Message):
    user_id = message.from_user.id
    products = await load_products_from_db(user_id)

    if not products:
        await message.answer("Пока нет продуктов. Добавь при вводе еды.")
        return

    text = "📦 Продукты:\n\n"
    for name, p in products.items():
        text += f"<b>{name}</b>: {p['calories']} ккал, {p['protein']} Б, {p['fat']} Ж, {p['carbs']} У\n"
    await message.answer(text)


# ❌ /delproduct — удалить продукт
@router.message(Command("delproduct"))
async def delete_product(message: Message):
    user_id = message.from_user.id
    products = await load_products_from_db(user_id)
    if not products:
        await message.answer("У тебя нет продуктов для удаления.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"delprod:{name}")]
        for name in products
    ])
    await message.answer("Выбери продукт для удаления:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("delprod:"))
async def confirm_delete_product(callback: CallbackQuery):
    name = callback.data.split(":")[1]
    await delete_product_from_db(callback.from_user.id, name)
    await callback.message.edit_text(f"❌ Продукт '{name}' удалён.")
    await callback.answer()


# ✏️ /editproduct — редактировать БЖУ
@router.message(Command("editproduct"))
async def edit_product_prompt(message: Message):
    await message.answer("Формат: <code>название;калории;белки;жиры;углеводы;соль;сахар</code>")


@router.message(F.text.contains(";"))
async def handle_product_edit(message: Message):
    try:
        parts = message.text.strip().split(";")
        if len(parts) != 7:
            raise ValueError
        name, cal, pr, fat, carb, salt, sugar = parts
        await update_product_in_db(
            message.from_user.id,
            name,
            float(cal), float(pr), float(fat), float(carb), float(salt), float(sugar)
        )
        await message.answer(f"✅ Продукт '{name}' обновлён")
    except:
        await message.answer("Ошибка формата. Введи снова как: <code>название;калории;белки;жиры;углеводы;соль;сахар</code>")
