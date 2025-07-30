from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from openpyxl import Workbook
from datetime import datetime
import sqlite3

router = Router()

@router.message(Command("export"))
async def export_data(message: Message):
    wb = Workbook()
    ws = wb.active
    ws.title = "Пример"
    ws.append(["Дата", "Данные"])
    ws.append([datetime.now().strftime("%Y-%m-%d"), "Экспортировано!"])

    filename = f"data/export_{message.from_user.id}.xlsx"
    wb.save(filename)
    await message.answer_document(open(filename, "rb"), caption="Готово!")
