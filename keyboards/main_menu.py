from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Данные пользователя")],
        [KeyboardButton(text="🍽 Рекомендации по КБЖУ")],
        [KeyboardButton(text="🧪 Анализы")],
        [KeyboardButton(text="🩻 Обследования")],
        [KeyboardButton(text="📊 Рекомендации")],
        [KeyboardButton(text="💊 Назначения врачей")],
        [KeyboardButton(text="❌ Удалить все данные")]
    ],
    resize_keyboard=True
)

# Подменю "Данные пользователя"
fill_data_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🖊 Ввести данные")],
        [KeyboardButton(text="👁️ Посмотреть текущие данные")],
        [KeyboardButton(text="✏️ Редактировать данные")],
        [KeyboardButton(text="❌ Удалить данные")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Подменю "Анализы"
analysis_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить анализ")],
        [KeyboardButton(text="📋 Посмотреть анализы")],
        [KeyboardButton(text="❌ Удалить анализ")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Подменю "Назначения врачей"
doctor_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить назначение")],
        [KeyboardButton(text="📋 Посмотреть назначения")],
        [KeyboardButton(text="✏️ Редактировать назначения")],
        [KeyboardButton(text="❌ Удалить назначения")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Подменю "Обследования"
examination_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить обследование")],
        [KeyboardButton(text="📋 Посмотреть обследования")],
        [KeyboardButton(text="✏️ Редактировать обследования")],
        [KeyboardButton(text="❌ Удалить обследования")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)