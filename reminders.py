from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import add_reminder, delete_reminder, get_reminders

router = Router(name="reminders")


# ⏰ /напоминание — формат и добавление
@router.message(Command("напоминание"))
async def reminder_info(message: Message):
    await message.answer(
        "Формат:\n"
        "<code>время;текст</code>\n"
        "Пример: <code>14:30;выпить воду</code>"
    )



@router.message(F.text.contains(";"))
async def add_new_reminder(message: Message):
    try:
        time, text = message.text.strip().split(";", maxsplit=1)
        time = time.strip()
        text = text.strip()
        if ";" in text:
            raise ValueError
        await add_reminder(message.from_user.id, time, text)
        await message.answer(f"⏰ Напоминание установлено: {time} — {text}")
    except:
        await message.answer("Ошибка формата. Пример: <code>08:00;утренний кофе</code>")


# 🗑 /удалитьнапоминание — список для удаления
@router.message(Command("удалитьнапоминание"))
async def delete_reminder_list(message: Message):
    reminders = await get_reminders(message.from_user.id)
    if not reminders:
        await message.answer("У тебя нет напоминаний")
        return

    text = "🗑 Напоминания:\n" + "\n".join(f"— {r['time']} — {r['text']}" for r in reminders)
    text += "\n\nЧтобы удалить: /удалитьвремя <часы:минуты>"
    await message.answer(text)


@router.message(F.text.startswith("/удалитьвремя "))
async def delete_reminder_by_time(message: Message):
    time = message.text.replace("/удалитьвремя ", "").strip()
    await delete_reminder(message.from_user.id, time)
    await message.answer(f"❌ Напоминание в {time} удалено")
