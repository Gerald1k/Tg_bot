from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os
import asyncio

# Загрузка токена из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Инициализация бота
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Клавиатура главного меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Заполнение данных")],
        [KeyboardButton(text="🍽 Рекомендации по КБЖУ")],
        [KeyboardButton(text="🧪 Добавить анализ")],
        [KeyboardButton(text="📊 Получить рекомендации")],
        [KeyboardButton(text="💊 Назначения врачей")],
        [KeyboardButton(text="🩻 Обследования")],
        [KeyboardButton(text="❌ Удалить пользователя")]
    ],
    resize_keyboard=True
)

# Клавиатура для подменю "Заполнение данных"
fill_data_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🖊 Ввести данные")],
        [KeyboardButton(text="✏️ Редактировать данные")],
        [KeyboardButton(text="❌ Удалить данные")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Обработка команды /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Привет! Я помогу вам вести вашу медицинскую карту.\n\n"
        "Здесь вы можете ввести свои данные, следить за анализами, получать рекомендации по питанию и многое другое. "
        "Чтобы начать, выберите одну из опций в главном меню ниже.",
        reply_markup=main_keyboard
    )

# Обработка команды "Заполнение данных"
@dp.message(F.text == "📝 Заполнение данных")
async def fill_data_handler(message: Message):
    await message.answer(
        "🔒 В этом разделе вы можете ввести свои данные, отредактировать их или удалить, если это необходимо.\n\n"
        "Выберите действие, которое хотите выполнить:",
        reply_markup=fill_data_keyboard
    )

# Обработка действия "Ввести данные"
@dp.message(F.text == "🖊 Ввести данные")
async def enter_data_handler(message: Message):
    await message.answer("🔽 Пожалуйста, начнем вводить ваши данные. Я буду поочередно задавать вопросы.")

# Обработка действия "Редактировать данные"
@dp.message(F.text == "✏️ Редактировать данные")
async def edit_data_handler(message: Message):
    await message.answer("✏️ Вы можете изменить свои данные.")

# Обработка действия "Удалить данные"
@dp.message(F.text == "❌ Удалить данные")
async def delete_data_handler(message: Message):
    await message.answer("⚠️ Вы уверены, что хотите удалить все данные? Напишите 'Да', чтобы подтвердить удаление.")

# Обработка возврата в главное меню
@dp.message(F.text == "⬅️ Назад")
async def back_to_main_menu(message: Message):
    await message.answer("🔙 Вы вернулись в главное меню. Выберите следующее действие.", reply_markup=main_keyboard)

# Точка входа
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
