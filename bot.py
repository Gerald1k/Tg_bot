from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
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
        [KeyboardButton(text="👁️ Посмотреть текущие данные")],
        [KeyboardButton(text="✏️ Редактировать данные")],
        [KeyboardButton(text="❌ Удалить данные")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# FSM-состояния для последовательного ввода данных
class DataStates(StatesGroup):
    fio = State()
    goal = State()
    sport = State()
    smoking = State()
    alcohol = State()
    chronic = State()
    heredity = State()
    clinical = State()

# /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    await message.answer(
        f"👋 Привет, {username}! Я помогу вам вести вашу медицинскую карту.\n\n"
        "Здесь вы можете ввести свои данные, следить за анализами, получать рекомендации по питанию и многое другое. "
        "Чтобы начать, выберите одну из опций в главном меню ниже.",
        reply_markup=main_keyboard
    )

# Главное меню → "Заполнение данных"
@dp.message(F.text == "📝 Заполнение данных")
async def fill_data_handler(message: Message):
    await message.answer(
        "🔒 В этом разделе вы можете ввести свои данные, отредактировать их или удалить, если это необходимо.\n\n"
        "Выберите действие, которое хотите выполнить:",
        reply_markup=fill_data_keyboard
    )

# Начало FSM: ввод данных
@dp.message(F.text == "🖊 Ввести данные")
async def enter_data_handler(message: Message, state: FSMContext):
    await state.set_state(DataStates.fio)
    await message.answer("Введите ваше ФИО:")

# Обработка ФИО
@dp.message(StateFilter(DataStates.fio))
async def process_fio(message: Message, state: FSMContext):
    await state.update_data(fio=message.text)
    # Переходим к выбору цели через inline-кнопки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Набор мышечной массы", callback_data="goal:Набор мышечной массы")],
        [InlineKeyboardButton(text="Поддержание формы",       callback_data="goal:Поддержание формы")],
        [InlineKeyboardButton(text="Снижение веса",           callback_data="goal:Снижение веса")],
    ])
    await state.set_state(DataStates.goal)
    await message.answer("Укажите вашу цель:", reply_markup=kb)

# Обработка выбора цели
@dp.callback_query(StateFilter(DataStates.goal), F.data.startswith("goal:"))
async def process_goal_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    goal = query.data.split(":", 1)[1]
    await state.update_data(goal=goal)
    await state.set_state(DataStates.sport)
    await query.message.edit_reply_markup()  # убираем кнопки
    await query.message.answer("Занимаетесь ли вы каким-либо спортом? Если да, укажите вид и частоту занятий:")

# Обработка спорта
@dp.message(StateFilter(DataStates.sport))
async def process_sport(message: Message, state: FSMContext):
    await state.update_data(sport=message.text)
    # inline-кнопки для курения
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да",  callback_data="smoking:Да")],
        [InlineKeyboardButton(text="Нет", callback_data="smoking:Нет")],
    ])
    await state.set_state(DataStates.smoking)
    await message.answer("Курите ли вы?", reply_markup=kb)

# Обработка выбора по курению
@dp.callback_query(StateFilter(DataStates.smoking), F.data.startswith("smoking:"))
async def process_smoking_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    smoking = query.data.split(":", 1)[1]
    await state.update_data(smoking=smoking)
    # inline-кнопки для алкоголя
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да",  callback_data="alcohol:Да")],
        [InlineKeyboardButton(text="Нет", callback_data="alcohol:Нет")],
    ])
    await state.set_state(DataStates.alcohol)
    await query.message.edit_reply_markup()
    await query.message.answer("Употребляете ли вы алкоголь?", reply_markup=kb)

# Обработка выбора по алкоголю
@dp.callback_query(StateFilter(DataStates.alcohol), F.data.startswith("alcohol:"))
async def process_alcohol_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    alcohol = query.data.split(":", 1)[1]
    await state.update_data(alcohol=alcohol)
    await query.message.edit_reply_markup()
    # Далее свободный ввод
    await state.set_state(DataStates.chronic)
    await query.message.answer("Есть ли у вас хронические болезни? Перечислите:")

# Обработка хронических болезней
@dp.message(StateFilter(DataStates.chronic))
async def process_chronic(message: Message, state: FSMContext):
    await state.update_data(chronic=message.text)
    await state.set_state(DataStates.heredity)
    await message.answer("Наследственная предрасположенность (перечислите, если есть):")

# Обработка наследственности
@dp.message(StateFilter(DataStates.heredity))
async def process_heredity(message: Message, state: FSMContext):
    await state.update_data(heredity=message.text)
    await state.set_state(DataStates.clinical)
    await message.answer("Клинические проявления (симптомы, жалобы):")

# Финальный шаг: вывод всех данных
@dp.message(StateFilter(DataStates.clinical))
async def process_clinical(message: Message, state: FSMContext):
    await state.update_data(clinical=message.text)
    data = await state.get_data()
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    summary = (
        f"<b>Вот введённые вами данные:</b>\n"
        f"👤 ФИО: {data['fio']}\n"
        f"🎯 Цель: {data['goal']}\n"
        f"🏅 Спорт: {data['sport']}\n"
        f"🚬 Курение: {data['smoking']}\n"
        f"🍷 Алкоголь: {data['alcohol']}\n"
        f"💉 Хронические болезни: {data['chronic']}\n"
        f"🧬 Наследственная предрасположенность: {data['heredity']}\n"
        f"🩺 Клинические проявления: {data['clinical']}\n"
        f"👤 Ваш аккаунт: {username}\n"
    )
    await message.answer(summary, reply_markup=main_keyboard)
    await state.clear()

# Остальные пункты меню
@dp.message(F.text == "✏️ Редактировать данные")
async def edit_data_handler(message: Message):
    await message.answer("✏️ Вы можете изменить свои данные.")

@dp.message(F.text == "❌ Удалить данные")
async def delete_data_handler(message: Message):
    await message.answer("⚠️ Вы уверены, что хотите удалить все данные? Напишите 'Да', чтобы подтвердить удаление.")

@dp.message(F.text == "⬅️ Назад")
async def back_to_main_menu(message: Message):
    await message.answer("🔙 Вы вернулись в главное меню. Выберите следующее действие.", reply_markup=main_keyboard)

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
