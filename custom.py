from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from database import add_custom_field, delete_custom_field, get_custom_fields

router = Router(name="custom")


# 🛠 /кастом — создать своё поле для /день
@router.message(Command("кастом"))
async def create_custom(message: Message):
    await message.answer(
        "Формат:\n"
        "<code>название;тип</code>\n\n"
        "Тип может быть: <code>да/нет</code>, <code>число</code> или <code>текст</code>"
    )


@router.message(F.text.contains(";"))
async def handle_custom_create(message: Message):
    try:
        name, type_ = message.text.strip().split(";", maxsplit=1)
        name = name.strip()
        type_ = type_.strip().lower()
        if type_ not in ["да/нет", "число", "текст"]:
            raise ValueError
        await add_custom_field(message.from_user.id, name, type_)
        await message.answer(f"🛠 Поле '{name}' ({type_}) добавлено в лог дня")
    except:
        await message.answer("Ошибка формата. Пример: <code>сон;число</code>")


# 🗑 /удалитькастом — удалить поле
@router.message(Command("удалитькастом"))
async def delete_custom(message: Message):
    fields = await get_custom_fields(message.from_user.id)
    if not fields:
        await message.answer("У тебя нет кастомных полей")
        return

    text = "🗑 Твои поля:\n" + "\n".join(f"— {field['name']} ({field['type']})" for field in fields)
    text += "\n\nЧтобы удалить: /удалить <название>"
    await message.answer(text)


@router.message(F.text.startswith("/удалить "))
async def delete_by_name(message: Message):
    name = message.text.replace("/удалить ", "").strip()
    await delete_custom_field(message.from_user.id, name)
    await message.answer(f"❌ Поле '{name}' удалено")
