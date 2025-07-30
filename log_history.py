from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from database import get_day_log, get_finance_logs, get_food_logs
from utils import export_logs_to_excel

router = Router(name="log_history")


# 📁 /отчёт — экспорт логов в Excel
@router.message(Command("отчёт"))
async def export_report(message: Message):
    user_id = message.from_user.id
    try:
        day_logs = await get_day_log(user_id)
        finance_logs = await get_finance_logs(user_id)
        food_logs = await get_food_logs(user_id)

        filepath = await export_logs_to_excel(user_id, day_logs, finance_logs, food_logs)
        with open(filepath, "rb") as file:
            await message.answer_document(file, caption="📁 Отчёт за всё время")
    except Exception as e:
        await message.answer("Ошибка при экспорте: " + str(e))
