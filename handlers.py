# 🫀 handlers.py — регистрация всех роутеров и базовые команды
from aiogram import Dispatcher, Bot, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

# 🧩 FSM
from fsm.add_habit import AddHabit

# 🧩 Импорт роутеров по модулям
from .day import router as day_router
from .finance_ import router as finance_router
from .food import router as food_router

# 🧠 Вспомогательные модули
from utils import user_habits
from database import load_habits_from_db

# 📦 Роутер текущего файла
router = Router()

# 🟢 Команда /start
@router.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    user_habits[user_id] = await load_habits_from_db(user_id)
    await message.answer(
        "Привет! Я бот, который помогает тебе отслеживать свою жизнь.\n\n"
        "🧭 Используй /help, чтобы посмотреть все команды."
    )

# 🟢 Команда /help
@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "Вот что я умею:\n\n"
        "📌 Основное:\n"
        "• /add — добавить привычку\n"
        "• /day — заполнить лог дня\n"
        "• /report — текущие привычки\n"
        "• /export — экспорт в Excel\n"
        "• /deletehabit — удалить привычку\n"
        "📅 Логи:\n"
        "• /history — последние записи\n"
        "• /week — за неделю\n"
        "• /month — за месяц\n"
        "🍎 Продукты:\n"
        "• /products — список продуктов\n"
        "💰 Финансы:\n"
        "• /finance — учёт расходов\n"
        "🔔 Напоминания:\n"
        "• /remind HH:MM — установить\n"
        "• /remind_off — отключить"
    )

# 🟢 Команда /add — запуск FSM
@router.message(Command("add"))
async def add_cmd(message: Message, state: FSMContext):
    await message.answer("Введи название привычки:")
    await state.set_state(AddHabit.waiting_for_name)

# 🧩 Регистрация всех роутеров
def register_handlers(dp: Dispatcher, bot: Bot):
    import config
    config.bot = bot

    dp.include_router(day_router)
    dp.include_router(finance_router)
    dp.include_router(food_router)
    dp.include_router(router)

    print("✅ Роутеры подключены: day, finance, food, core")
