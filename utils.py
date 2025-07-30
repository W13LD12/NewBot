import re
from datetime import datetime

# 🫀 Проверка корректности времени (в формате HH:MM)
def is_valid_time_format(time_str):
    return bool(re.match(r"^\d{2}:\d{2}$", time_str))


# 🫀 Получение текущей даты (в формате YYYY-MM-DD)
def get_today():
    return datetime.now().strftime("%Y-%m-%d")


# 🫀 Получение текущего времени (в формате HH:MM)
def get_current_time():
    return datetime.now().strftime("%H:%M")


# 🫀 Быстрая генерация Markdown-ссылки (например, на Excel-файл)
def get_markdown_link(file_path, label="Скачать файл"):
    return f"[{label}](file://{file_path})"


# 🫀 Сжатие длинного текста (например, логов или JSON)
def truncate_text(text, limit=1000):
    return text if len(text) <= limit else text[:limit] + "..."


# 🫀 Проверка, является ли строка числом (с плавающей точкой)
def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
