from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    CallbackQuery
)
from aiogram.filters import CommandStart, StateFilter
from aiogram.filters.command import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError
from dotenv import load_dotenv
import os
import asyncio
from db import async_session, UserData, Analysis, AnalyzesMem, Recommendation, DoctorAppointment, InstrumentalExamination
from sqlalchemy import select, delete, func, desc
from datetime import datetime, date, timedelta
import dateparser
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import tempfile
import re

# Загрузка реального токена из .env
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
        [KeyboardButton(text="📝 Данные пользователя")],
        [KeyboardButton(text="🍽 Рекомендации по КБЖУ")],
        [KeyboardButton(text="🧪 Анализы")],
        [KeyboardButton(text="📊 Рекомендации")],
        [KeyboardButton(text="💊 Назначения врачей")],
        [KeyboardButton(text="🩻 Обследования")],
        [KeyboardButton(text="❌ Удалить все данные")]
    ],
    resize_keyboard=True
)

# Клавиатура для подменю "Данные пользователя"
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
# Клавиатура для подменю "Анализы"
analysis_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить анализ")],
        [KeyboardButton(text="📋 Посмотреть анализы")],
        [KeyboardButton(text="❌ Удалить анализ")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура для подменю "Назначения врачей"
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

# Клавиатура для подменю "Обследования"
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

# FSM-состояния для последовательного ввода данных
class DataStates(StatesGroup):
    fio = State()
    goal = State()
    sport = State()
    height = State()    # Новый шаг: рост
    weight = State()    # Новый шаг: вес
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
#----------------------------------------------------------------------------------------------------------------------------------------------------------#
# Главное меню → "Данные пользователя"
@dp.message(F.text == "📝 Данные пользователя")
async def fill_data_handler(message: Message):
    await message.answer(
        "🔒 В этом разделе вы можете ввести свои данные, отредактировать их или удалить, если это необходимо.\n\n"
        "Выберите действие, которое хотите выполнить:",
        reply_markup=fill_data_keyboard
    )

# Начало FSM: ввод ФИО
@dp.message(F.text == "🖊 Ввести данные")
async def enter_data_handler(message: Message, state: FSMContext):
    await state.set_state(DataStates.fio)
    await message.answer("Введите ваше ФИО:")

# Обработка ФИО → выбор цели
@dp.message(StateFilter(DataStates.fio))
async def process_fio(message: Message, state: FSMContext):
    await state.update_data(fio=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Набор мышечной массы", callback_data="goal:Набор мышечной массы")],
        [InlineKeyboardButton(text="Поддержание формы",       callback_data="goal:Поддержание формы")],
        [InlineKeyboardButton(text="Снижение веса",           callback_data="goal:Снижение веса")],
    ])
    await state.set_state(DataStates.goal)
    await message.answer("Укажите вашу цель:", reply_markup=kb)

# Обработка выбора цели → спорт
@dp.callback_query(StateFilter(DataStates.goal), F.data.startswith("goal:"))
async def process_goal_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    goal = query.data.split(":", 1)[1]
    await state.update_data(goal=goal)
    await state.set_state(DataStates.sport)
    await query.message.edit_reply_markup()
    await query.message.answer("Занимаетесь ли вы каким-либо спортом? Если да, укажите вид и частоту занятий:")

# Обработка спорта → рост
@dp.message(StateFilter(DataStates.sport))
async def process_sport(message: Message, state: FSMContext):
    await state.update_data(sport=message.text)
    await state.set_state(DataStates.height)
    await message.answer("Введите ваш рост (в сантиметрах):")

# Обработка роста → вес
@dp.message(StateFilter(DataStates.height))
async def process_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text)
    await state.set_state(DataStates.weight)
    await message.answer("Введите ваш вес (в килограммах):")

# Обработка веса → курение
@dp.message(StateFilter(DataStates.weight))
async def process_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да",  callback_data="smoking:Да")],
        [InlineKeyboardButton(text="Нет", callback_data="smoking:Нет")],
    ])
    await state.set_state(DataStates.smoking)
    await message.answer("Курите ли вы?", reply_markup=kb)

# Обработка курения → алкоголь
@dp.callback_query(StateFilter(DataStates.smoking), F.data.startswith("smoking:"))
async def process_smoking_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    smoking = query.data.split(":", 1)[1]
    await state.update_data(smoking=smoking)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да",  callback_data="alcohol:Да")],
        [InlineKeyboardButton(text="Нет", callback_data="alcohol:Нет")],
    ])
    await state.set_state(DataStates.alcohol)
    await query.message.edit_reply_markup()
    await query.message.answer("Употребляете ли вы алкоголь?", reply_markup=kb)

# Обработка алкоголя → хронические болезни
@dp.callback_query(StateFilter(DataStates.alcohol), F.data.startswith("alcohol:"))
async def process_alcohol_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    alcohol = query.data.split(":", 1)[1]
    await state.update_data(alcohol=alcohol)
    await query.message.edit_reply_markup()
    await state.set_state(DataStates.chronic)
    await query.message.answer("Есть ли у вас хронические болезни? Перечислите:")

# Обработка хронических болезней → наследственность
@dp.message(StateFilter(DataStates.chronic))
async def process_chronic(message: Message, state: FSMContext):
    await state.update_data(chronic=message.text)
    await state.set_state(DataStates.heredity)
    await message.answer("Наследственная предрасположенность (перечислите, если есть):")

# Обработка наследственности → клиника
@dp.message(StateFilter(DataStates.heredity))
async def process_heredity(message: Message, state: FSMContext):
    await state.update_data(heredity=message.text)
    await state.set_state(DataStates.clinical)
    await message.answer("Клинические проявления (симптомы, жалобы):")

# Финальный шаг: сохранение и вывод
@dp.message(StateFilter(DataStates.clinical))
async def process_clinical(message: Message, state: FSMContext):
    await state.update_data(clinical=message.text)
    data = await state.get_data()

    # Сохранение в БД (предполагается, что в модели есть поля height и weight)
    async with async_session() as session:
        async with session.begin():
            user_data = UserData(
                telegram_id=message.from_user.id,
                username=message.from_user.username or message.from_user.full_name,
                full_name=data['fio'],
                goal=data['goal'],
                sport=data['sport'],
                height=data['height'],
                weight=data['weight'],
                smoking=data['smoking'],
                alcohol=data['alcohol'],
                diseases=data['chronic'],
                heredity=data['heredity'],
                symptoms=data['clinical']
            )
            session.add(user_data)
        await session.commit()

    await message.answer("Ваши данные были успешно сохранены!", reply_markup=main_keyboard)
    await state.clear()

# Остальные пункты меню  
@dp.message(F.text == "👁️ Посмотреть текущие данные")
async def view_data_handler(message: Message):
    # Открываем асинхронную сессию
    async with async_session() as session:
        async with session.begin():
            # Ищем пользователя по telegram_id
            result = await session.execute(
                select(UserData).where(UserData.telegram_id == message.from_user.id)
            )
            user = result.scalars().first()

    if not user:
        # Если данных нет — приглашаем сначала их ввести
        await message.answer(
            "Данные не найдены. Пожалуйста, сначала введите ваши данные.",
            reply_markup=fill_data_keyboard
        )
        return

    # Формируем сводку из полей модели
    summary = (
        f"<b>Ваши текущие данные:</b>\n"
        f"👤 ФИО: {user.full_name}\n"
        f"🎯 Цель: {user.goal}\n"
        f"🏅 Спорт: {user.sport}\n"
        f"📏 Рост: {user.height} см\n"
        f"⚖️ Вес: {user.weight} кг\n"
        f"🚬 Курение: {user.smoking}\n"
        f"🍷 Алкоголь: {user.alcohol}\n"
        f"💉 Хронические болезни: {user.diseases}\n"
        f"🧬 Наследственная предрасположенность: {user.heredity}\n"
        f"🩺 Клинические проявления: {user.symptoms}\n"
    )
    await message.answer(summary, reply_markup=fill_data_keyboard)

# FSM-состояния для редактирования данных
class EditStates(StatesGroup):
    field = State()
    value = State()

# Словари для отображения и обновления полей
field_display_map = {
    'fio': 'ФИО',
    'goal': 'Цель',
    'sport': 'Спорт',
    'height': 'Рост',
    'weight': 'Вес',
    'smoking': 'Курение',
    'alcohol': 'Алкоголь',
    'chronic': 'Хронические болезни',
    'heredity': 'Наследственность',
    'clinical': 'Клинические проявления',
}
field_model_attr = {
    'fio': 'full_name',
    'goal': 'goal',
    'sport': 'sport',
    'height': 'height',
    'weight': 'weight',
    'smoking': 'smoking',
    'alcohol': 'alcohol',
    'chronic': 'diseases',
    'heredity': 'heredity',
    'clinical': 'symptoms',
}
field_prompt = {
    'fio': "Введите новое ФИО:",
    'goal': "Укажите новую цель:",
    'sport': "Укажите новый вид и частоту занятий спортом:",
    'height': "Введите новый рост (в сантиметрах):",
    'weight': "Введите новый вес (в килограммах):",
    'smoking': "Курите ли вы? (Да/Нет):",
    'alcohol': "Употребляете ли вы алкоголь? (Да/Нет):",
    'chronic': "Перечислите ваши хронические болезни:",
    'heredity': "Укажите наследственную предрасположенность:",
    'clinical': "Опишите клинические проявления (симптомы, жалобы):",
}

# При старте редактирования ничего не меняется:
@dp.message(F.text == "✏️ Редактировать данные")
async def edit_data_handler(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=field_display_map[f], callback_data=f"edit:{f}")]
            for f in field_display_map
        ]
    )
    await state.set_state(EditStates.field)
    await message.answer("Выберите, какое поле вы хотите отредактировать:", reply_markup=kb)

# Пользователь выбирает поле
@dp.callback_query(StateFilter(EditStates.field), F.data.startswith("edit:"))
async def process_edit_field(query: CallbackQuery, state: FSMContext):
    await query.answer()
    field = query.data.split(":", 1)[1]
    await state.update_data(field=field)
    await query.message.edit_reply_markup()  # убираем кнопки

    # Если цель — показываем три варианта
    if field == 'goal':
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Набор мышечной массы", callback_data="edit_goal:Набор мышечной массы")],
            [InlineKeyboardButton(text="Поддержание формы",       callback_data="edit_goal:Поддержание формы")],
            [InlineKeyboardButton(text="Снижение веса",           callback_data="edit_goal:Снижение веса")],
        ])
        await query.message.answer("Выберите новую цель:", reply_markup=kb)
        await state.set_state(EditStates.value)
        return

    # Если курение — вариант Да/Нет
    if field == 'smoking':
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да",  callback_data="edit_smoking:Да")],
            [InlineKeyboardButton(text="Нет", callback_data="edit_smoking:Нет")],
        ])
        await query.message.answer("Курите ли вы?", reply_markup=kb)
        await state.set_state(EditStates.value)
        return

    # Если алкоголь — вариант Да/Нет
    if field == 'alcohol':
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да",  callback_data="edit_alcohol:Да")],
            [InlineKeyboardButton(text="Нет", callback_data="edit_alcohol:Нет")],
        ])
        await query.message.answer("Употребляете ли вы алкоголь?", reply_markup=kb)
        await state.set_state(EditStates.value)
        return

    # Для всех остальных полей — свободный ввод
    await state.set_state(EditStates.value)
    await query.message.answer(field_prompt[field])

# Обработка callback‑ответа для goal/smoking/alcohol
@dp.callback_query(StateFilter(EditStates.value), F.data.startswith("edit_goal:"))
@dp.callback_query(StateFilter(EditStates.value), F.data.startswith("edit_smoking:"))
@dp.callback_query(StateFilter(EditStates.value), F.data.startswith("edit_alcohol:"))
async def process_edit_choice_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    prefix, new_value = query.data.split(":", 1)
    data = await state.get_data()
    field = data['field']

    # Обновляем в БД
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(UserData).where(UserData.telegram_id == query.from_user.id)
            )
            user = result.scalars().first()
            if user:
                setattr(user, field_model_attr[field], new_value)
                session.add(user)
        await session.commit()

    await query.message.edit_reply_markup()
    await query.message.answer(
        f"✅ Поле «{field_display_map[field]}» успешно обновлено на «{new_value}»!",
        reply_markup=fill_data_keyboard
    )
    await state.clear()

# Обработка свободного ввода для остальных полей
@dp.message(StateFilter(EditStates.value))
async def process_edit_text_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    new_value = message.text

    # Обновляем в БД
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(UserData).where(UserData.telegram_id == message.from_user.id)
            )
            user = result.scalars().first()
            if user:
                setattr(user, field_model_attr[field], new_value)
                session.add(user)
        await session.commit()

    await message.answer(
        f"✅ Поле «{field_display_map[field]}» успешно обновлено!",
        reply_markup=fill_data_keyboard
    )
    await state.clear()


# Добавим FSM‑стейт для удаления
class DeleteStates(StatesGroup):
    confirm = State()

# Обработчик кнопки "❌ Удалить данные"
@dp.message(F.text == "❌ Удалить данные")
async def delete_data_handler(message: Message, state: FSMContext):
    # Ставим состояние подтверждения
    await state.set_state(DeleteStates.confirm)

    # Корректно создаём ReplyKeyboardMarkup и KeyboardButton с ключевыми аргументами:
    confirm_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬅️ Отмена")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "⚠️ Вы уверены, что хотите полностью удалить все ваши данные?\n"
        "Напишите строго «Да», чтобы подтвердить удаление.",
        reply_markup=confirm_kb
    )


# Обработка подтверждения/отмены
@dp.message(StateFilter(DeleteStates.confirm))
async def process_delete_confirmation(message: Message, state: FSMContext):
    text = message.text.strip().lower()

    if text == "да":
        # Удаляем строку пользователя
        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(UserData)
                    .where(UserData.telegram_id == message.from_user.id)
                )
            await session.commit()

        await message.answer("✅ Ваши данные успешно удалены!", reply_markup=main_keyboard)

    else:
        await message.answer("❌ Удаление отменено. Ваши данные сохранены.", reply_markup=fill_data_keyboard)

    await state.clear()


@dp.message(F.text == "⬅️ Назад")
async def back_to_main_menu(message: Message):
    await message.answer("🔙 Вы вернулись в главное меню. Выберите следующее действие.", reply_markup=main_keyboard)
#----------------------------------------------------------------------------------------------------------------------------------------------------------#
@dp.message(F.text == "🍽 Рекомендации по КБЖУ")
async def kbju_recommendation(message: Message):
    # достаём из БД вес и цель пользователя
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(UserData).where(UserData.telegram_id == message.from_user.id)
            )
            user = result.scalars().first()

    if not user:
        await message.answer(
            "❗️ Данных не найдено. Сначала заполните профиль через 📝 Данные пользователя.",
            reply_markup=main_keyboard
        )
        return

    try:
        weight = float(user.weight)
    except (TypeError, ValueError):
        await message.answer(
            "⚠️ Неверный формат веса в базе. Пожалуйста, обновите его в разделе 📝 Данные пользователя → ✏️ Редактировать данные → Вес.",
            reply_markup=main_keyboard
        )
        return

    goal = user.goal

    # Примитивные формулы для каждого сценария
    if goal == "Набор мышечной массы":
        proteins = weight * 1.5
        fats     = weight - 10
        carbs    = weight * 4
        carbs2   = weight * 3
        calories = proteins * 4 + fats * 9 + carbs * 4
        calories2 = proteins * 4 + fats * 9 + carbs2 * 4
        expected_change = (calories - calories2) * 30 / 7.9
        change_text = f"Прогнозируемый прирост в месяц: {int(expected_change)} г"
    elif goal == "Снижение веса":
        proteins = weight * 1.5
        fats     = weight - 10
        carbs    = weight * 1.5
        carbs2   = weight * 3
        calories = proteins * 4 + fats * 9 + carbs * 4
        calories2 = proteins * 4 + fats * 9 + carbs2 * 4
        expected_change = abs(calories - calories2) * 30 / 7.9
        change_text = f"Прогнозируемая потеря в месяц: {int(expected_change)} г"
    else:  # Поддержание формы
        proteins = weight * 1.5
        fats     = weight - 10
        carbs    = weight * 3
        calories = proteins * 4 + fats * 9 + carbs * 4
        change_text = "Прогнозируемых изменений в массе нет"

    # Собираем и отправляем сообщение
    text = (
        f"🏋️‍♂️ <b>Рекомендации по КБЖУ</b>\n\n"
        f"📏 Ваш вес: {weight:.1f} кг\n"
        f"🎯 Цель: {goal}\n\n"
        f"🥩 Белки: {int(proteins)} г\n"
        f"🧈 Жиры: {int(fats)} г\n"
        f"🍞 Углеводы: {int(carbs)} г\n"
        f"🔥 Калории: {int(calories)} ккал\n\n"
        f"🔄 {change_text}"
    )
    await message.answer(text, reply_markup=main_keyboard)

class AddAnalysis(StatesGroup):
    date = State()
    select_group = State()
    select_analysis = State()
    select_variant = State()
    result = State()
#----------------------------------------------------------------------------------------------------------------------------------------------------------#
@dp.message(F.text == "🧪 Анализы")
async def analyses_menu_handler(message: Message):
    await message.answer("Выберите действие с анализами:", reply_markup=analysis_keyboard)



@dp.message(F.text == "➕ Добавить анализ")
async def start_add_analysis(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Введите дату сдачи анализов (дд.мм.гггг, 'сегодня', 'вчера'):"
    )
    await state.set_state(AddAnalysis.date)


@dp.message(AddAnalysis.date)
async def process_date(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    try:
        if text in ['сегодня', 'today']:
            parsed_date = date.today()
        elif text in ['вчера', 'yesterday']:
            parsed_date = date.today() - timedelta(days=1)
        else:
            dt = dateparser.parse(text, languages=['ru', 'en'])
            if not dt:
                raise ValueError
            parsed_date = dt.date()

        await state.update_data(date=parsed_date)

        async with async_session() as session:
            q = select(AnalyzesMem.group_name).distinct()
            res = await session.execute(q)
            groups = [r[0] for r in res.all()]

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=g, callback_data=f"group|{g}")] for g in groups
            ] + [[InlineKeyboardButton(text="✅ Закончить ввод", callback_data="finish")]]
        )
        await message.answer("Выберите группу анализа:", reply_markup=kb)
        await state.set_state(AddAnalysis.select_group)
    except Exception:
        await message.answer(
            "❌ Не удалось распознать дату. Введите в формате дд.мм.гггг, 'сегодня' или 'вчера'."
        )


@dp.callback_query(F.data.startswith('group|'), AddAnalysis.select_group)
async def choose_group(callback: CallbackQuery, state: FSMContext):
    group = callback.data.split("|", 1)[1]
    await state.update_data(group=group)

    async with async_session() as session:
        q = select(AnalyzesMem.name).where(AnalyzesMem.group_name == group).distinct()
        res = await session.execute(q)
        names = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"analysis|{n}")] for n in names
        ] + [[InlineKeyboardButton(text="🔙 Назад к группам", callback_data="back_to_groups")]]
    )
    await callback.message.answer(f"Группа: {group}. Выберите анализ:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_analysis)
    await callback.answer()


@dp.callback_query(F.data == 'back_to_groups', AddAnalysis.select_analysis)
async def back_to_groups(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        q = select(AnalyzesMem.group_name).distinct()
        res = await session.execute(q)
        groups = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"group|{g}")] for g in groups
        ] + [[InlineKeyboardButton(text="✅ Закончить ввод", callback_data="finish")]]
    )
    await callback.message.answer("Выберите группу анализа:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_group)
    await callback.answer()


@dp.callback_query(F.data.startswith('analysis|'), AddAnalysis.select_analysis)
async def choose_analysis(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split("|", 1)[1]
    data = await state.get_data()
    group = data.get("group")

    async with async_session() as session:
        q = select(AnalyzesMem).where(
            AnalyzesMem.group_name == group,
            AnalyzesMem.name == name
        )
        res = await session.execute(q)
        variants = res.scalars().all()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{v.unit} ({v.reference_values})", callback_data=f"variant|{v.id}")] for v in variants
        ] + [[InlineKeyboardButton(text="🔙 Назад к анализам", callback_data="back_to_analyses")]]
    )
    await callback.message.answer(f"Анализ: {name}. Выберите Единицы измерения:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_variant)
    await callback.answer()


@dp.callback_query(F.data == 'back_to_analyses', AddAnalysis.select_variant)
async def back_to_analyses(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    group = data.get("group")

    async with async_session() as session:
        q = select(AnalyzesMem.name).where(AnalyzesMem.group_name == group).distinct()
        res = await session.execute(q)
        names = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"analysis|{n}")] for n in names
        ] + [[InlineKeyboardButton(text="🔙 Назад к группам", callback_data="back_to_groups")]]
    )
    await callback.message.answer(f"Группа: {group}. Выберите анализ:", reply_markup=kb)
    await state.set_state(AddAnalysis.select_analysis)
    await callback.answer()


@dp.callback_query(F.data.startswith('variant|'), AddAnalysis.select_variant)
async def choose_variant(callback: CallbackQuery, state: FSMContext):
    mem_id = int(callback.data.split("|", 1)[1])
    async with async_session() as session:
        mem = await session.get(AnalyzesMem, mem_id)

    # Сохраняем в state все, что нужно для пересчёта и сохранения
    await state.update_data(
        mem_id=mem_id,
        name=mem.name,
        # коэффициент пересчёта в стандартную единицу
        conversion_to_standard=mem.conversion_to_standard,
        # стандартная единица и её референсные значения
        standard_unit=mem.standard_unit,
        standard_reference=mem.standard_reference
    )

    await callback.message.answer(
        f"Вы выбрали: {mem.name} — {mem.unit} ({mem.reference_values}).\nВведите результат анализа(например 5.6):"
    )
    await state.set_state(AddAnalysis.result)
    await callback.answer()


@dp.message(AddAnalysis.result)
async def process_result(message: Message, state: FSMContext):
    data = await state.get_data()
    raw_val = float(message.text.strip())

    # Пересчитываем
    standardized_val = raw_val * data['conversion_to_standard']

    async with async_session() as session:
        async with session.begin():
            new = Analysis(
                telegram_id=message.from_user.id,
                name=data['name'],
                group_name=data['group'],
                # сохраняем уже стандартные единицы и референс
                units=data['standard_unit'],
                reference=data['standard_reference'],
                result=str(standardized_val),
                date=data['date']
            )
            session.add(new)

    # Дальше по старой логике — показываем клавиатуру с группами
    async with async_session() as session:
        q = select(AnalyzesMem.group_name).distinct()
        res = await session.execute(q)
        groups = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"group|{g}")]
            for g in groups
        ] + [[InlineKeyboardButton(text="✅ Закончить ввод", callback_data="finish")]]
    )
    await message.answer(
        f"✅ Сохранено: {data['name']} = {standardized_val} {data['standard_unit']}. "
        "Выберите следующий анализ или закончите:",
        reply_markup=kb
    )
    await state.set_state(AddAnalysis.select_group)

@dp.message(AddAnalysis.result)
async def process_result(message: Message, state: FSMContext):
    data = await state.get_data()
    result_val = message.text.strip()

    # Пересчитываем результат с учетом коэффициента
    result_val = float(result_val) * data['conversion_factor']

    parsed_date = data['date']
    group = data['group']

    async with async_session() as session:
        async with session.begin():
            new = Analysis(
                telegram_id=message.from_user.id,
                name=data['name'],
                group_name=group,
                reference=data['reference_values'],
                units=data['unit'],
                result=result_val,
                date=parsed_date
            )
            session.add(new)

    async with async_session() as session:
        q = select(AnalyzesMem.group_name).distinct()
        res = await session.execute(q)
        groups = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"group|{g}")] for g in groups
        ] + [[InlineKeyboardButton(text="✅ Закончить ввод", callback_data="finish")]]
    )
    await message.answer(
        f"✅ Сохранено: {data['name']} = {result_val}. Выберите следующий анализ или закончите:",
        reply_markup=kb
    )
    await state.set_state(AddAnalysis.select_group)


@dp.callback_query(F.data == "finish", AddAnalysis.select_group)
async def finish_adding(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Ввод анализов завершён.", reply_markup=analysis_keyboard)
    await state.clear()
    await callback.answer()



# --------------- Просмотр анализов -----------------

pdfmetrics.registerFont(
    TTFont('ArialUnicode', r'C:\Windows\Fonts\arial.ttf')
)

@dp.message(F.text == "📋 Посмотреть анализы")
async def show_analysis_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Все анализы", callback_data="view_option|all")],
        [InlineKeyboardButton(text="По дате сдачи", callback_data="view_option|date")],
        [InlineKeyboardButton(text="Динамика", callback_data="view_option|trend")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_view")]
    ])
    await message.answer("Выберите опцию отображения анализов:", reply_markup=kb)

# 2. Обработка выбора опции
@dp.callback_query(F.data.startswith("view_option|"))
async def handle_view_option(callback: CallbackQuery):
    option = callback.data.split("|", 1)[1]
    # Опция "Все анализы"
    if option == "all":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Сообщением", callback_data="all_msg")],
            [InlineKeyboardButton(text="PDF", callback_data="all_pdf")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")]
        ])
        await callback.message.answer("Как вы хотите получить все анализы?", reply_markup=kb)

    # Опция "По дате сдачи"
    elif option == "date":
        async with async_session() as session:
            q = select(Analysis.date).where(
                Analysis.telegram_id == callback.from_user.id
            ).distinct().order_by(desc(Analysis.date))
            res = await session.execute(q)
            dates = [r[0] for r in res.all()]
        if not dates:
            await callback.message.answer("У вас нет ни одного анализа.")
        else:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=d.strftime("%d.%m.%Y"), callback_data=f"view_date|{d.isoformat()}")]
                    for d in dates
                ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="show_menu")]]
            )
            await callback.message.answer("Выберите дату сдачи:", reply_markup=kb)

    # Опция "Динамика"
    elif option == "trend":
        # Выводим группы анализов, как в текущей реализации
        async with async_session() as session:
            q = select(Analysis.group_name).where(
                Analysis.telegram_id == callback.from_user.id
            ).distinct()
            res = await session.execute(q)
            groups = [r[0] for r in res.all()]
        if not groups:
            await callback.message.answer("📋 У вас ещё нет ни одного анализа.")
        else:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=g, callback_data=f"view_group|{g}")]
                    for g in groups
                ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_view")]]
            )
            await callback.message.answer(
                "Выберите группу анализов для просмотра:", reply_markup=kb
            )
    await callback.answer()

# 3. Вывод всех анализов сообщением (последние результаты)
@dp.callback_query(F.data == "all_msg")
async def all_msg(callback: CallbackQuery):
    async with async_session() as session:
        subq = select(
            Analysis.name,
            func.max(Analysis.date).label("max_date")
        ).where(
            Analysis.telegram_id == callback.from_user.id
        ).group_by(Analysis.name).subquery()
        q = select(
            Analysis.name,
            Analysis.result,
            Analysis.reference,
            Analysis.date
        ).join(
            subq,
            (Analysis.name == subq.c.name) & (Analysis.date == subq.c.max_date)
        )
        res = await session.execute(q)
        rows = res.all()

    if not rows:
        await callback.message.answer("У вас нет ни одного анализа.")
        await callback.answer()
        return

    text = "<b>Последние результаты по всем анализам:</b>\n"
    for name, result, reference, date in rows:
        # приводим к числу (учёт 4,5 и 4.5)
        res_num = None
        if result:
            try:
                res_num = float(result.replace(',', '.'))
            except ValueError:
                pass

        # парсим диапазон reference
        min_ref = max_ref = None
        if reference:
            parts = re.split(r'[^0-9\.]+', reference)
            nums = [p.replace(',', '.') for p in parts if p]
            if len(nums) >= 2:
                try:
                    min_ref, max_ref = float(nums[0]), float(nums[1])
                except ValueError:
                    pass

        # выбираем эмодзи
        if res_num is not None and min_ref is not None and max_ref is not None:
            emoji = '🟢' if min_ref <= res_num <= max_ref else '🔴'
        else:
            emoji = ''

        text += f"{emoji}{name} = {result} ({date.strftime('%d.%m.%Y')})\n"

    await callback.message.answer(text)
    await callback.answer()

# 4. Вывод всех анализов в PDF (два последних результата)
@dp.callback_query(F.data == "all_pdf")
async def all_pdf(callback: CallbackQuery):
    # --- Получаем данные ---
    async with async_session() as session:
        q = (
            select(Analysis)
            .where(Analysis.telegram_id == callback.from_user.id)
            .order_by(Analysis.name, desc(Analysis.date))
        )
        res = await session.execute(q)
        analyses = res.scalars().all()

    # --- Группируем по названию ---
    grouped = {}
    for a in analyses:
        grouped.setdefault(a.name, []).append(a)

    # --- Подготовка таблицы и стилей ---
    data = [[
        'Анализ', 'Последний результат (дата)',
        'Предыдущий результат (дата)', 'Референс', 'Ед. изм.'
    ]]
    styles = [
        ('FONTNAME',   (0,0), (-1,-1), 'ArialUnicode'),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
    ]

    # Шаблон для Paragraph
    stylesheet = getSampleStyleSheet()
    body = stylesheet['BodyText']
    body.fontName = 'ArialUnicode'
    body.fontSize = 10

    row = 1
    for name, items in grouped.items():
        last = items[0]
        prev = items[1] if len(items) > 1 else None

        # Функция для создания окрашенного Paragraph
        def make_para(item):
            txt = item.result
            date_str = item.date.strftime('%d.%m.%Y')
            color = None
            try:
                val = float(item.result.replace(',', '.'))
                parts = re.split(r'[^0-9,\.]+', item.reference or '')
                nums = [p.replace(',', '.') for p in parts if p]
                if len(nums) >= 2:
                    lo, hi = map(float, nums[:2])
                    color = 'green' if lo <= val <= hi else 'red'
            except:
                pass

            if color:
                # цветим только число, дату оставляем чёрной
                return Paragraph(
                    f'<font name="ArialUnicode">'
                    f'<font color="{color}">{txt}</font> '
                    f'({date_str})'
                    f'</font>',
                    body
                )
            else:
                return Paragraph(f'{txt} ({date_str})', body)

        last_para = make_para(last)
        prev_para = make_para(prev) if prev else Paragraph('—', body)

        data.append([
            Paragraph(name, body),
            last_para,
            prev_para,
            Paragraph(last.reference or '—', body),
            Paragraph(last.units or '—', body),
        ])
        row += 1

    # --- Генерируем PDF ---
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    tbl = Table(
        data,
        colWidths=[80, 150, 150, 70, 60],  # 80 пунктов для столбца "Ед. изм."
        repeatRows=1
    )
    tbl.setStyle(TableStyle(styles))
    doc.build([tbl])
    buf.seek(0)

    # --- Отправляем пользователю ---
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
        tf.write(buf.read())
        path = tf.name

    await callback.message.answer_document(FSInputFile(path, filename='all_analyses.pdf'))
    await callback.answer()
    os.remove(path)

# 5. Вывод по дате
@dp.callback_query(F.data.startswith("view_date|"))
async def view_date(callback: CallbackQuery):
    iso = callback.data.split("|", 1)[1]
    date = datetime.fromisoformat(iso).date()
    async with async_session() as session:
        q = select(Analysis.name, Analysis.result, Analysis.reference).where(
            Analysis.telegram_id == callback.from_user.id,
            Analysis.date == date
        )
        res = await session.execute(q)
        rows = res.all()

    if not rows:
        await callback.message.answer("Нет записей за выбранную дату.")
    else:
        text = f"<b>Результаты анализов за {date.strftime('%d.%m.%Y')}:</b>\n"
        for name, result, reference in rows:
            # пытаемся привести результат к числу (учёт 4,5 и 4.5)
            res_num = None
            if result:
                try:
                    res_num = float(result.replace(',', '.'))
                except ValueError:
                    pass

            # парсим границы референсного диапазона
            min_ref = max_ref = None
            if reference:
                parts = re.split(r'[^0-9,\.]+', reference)
                nums = [p.replace(',', '.') for p in parts if p]
                if len(nums) >= 2:
                    try:
                        min_ref, max_ref = float(nums[0]), float(nums[1])
                    except ValueError:
                        pass

            # выбираем эмодзи
            if res_num is not None and min_ref is not None and max_ref is not None:
                emoji = '🟢' if min_ref <= res_num <= max_ref else '🔴'
            else:
                emoji = ''

            text += f"{name} = {emoji}{result} ({reference})\n"
        await callback.message.answer(text)
        await callback.answer()

# 6. Группы и отдельный анализ (динамика) — текущая реализация
@dp.callback_query(F.data.startswith("view_group|"))
async def view_group(callback: CallbackQuery):
    group = callback.data.split("|", 1)[1]
    async with async_session() as session:
        q = select(Analysis.name).where(
            Analysis.telegram_id == callback.from_user.id,
            Analysis.group_name == group
        ).distinct()
        res = await session.execute(q)
        names = [r[0] for r in res.all()]

    if not names:
        await callback.message.answer(
            "В выбранной группе у вас ещё нет ни одного анализа.",
            reply_markup=None
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=n, callback_data=f"view_analysis|{n}")]
                for n in names
            ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="cancel_view")]]
        )
        await callback.message.answer(
            f"Группа: {group}. Выберите анализ:",
            reply_markup=kb
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("view_analysis|"))
async def view_analysis(callback: CallbackQuery):
    name = callback.data.split("|", 1)[1]
    async with async_session() as session:
        q = select(Analysis).where(
            Analysis.telegram_id == callback.from_user.id,
            Analysis.name == name
        ).order_by(desc(Analysis.date))
        res = await session.execute(q)
        analyses = res.scalars().all()

    if not analyses:
        await callback.message.answer(
            "У вас нет записей для этого анализа."
        )
    else:
        text = f"<b>Анализы {name}:</b>\n\n"
        for a in analyses:
            dt = a.date.strftime("%d.%m.%Y") if a.date else '—'
            res_num = None
            if a.result:
                try:
                    res_num = float(a.result.replace(',', '.'))
                except ValueError:
                    pass

            # парсим границы нормы из строки reference, например "60-80"
            min_ref = max_ref = None
            if a.reference:
                parts = re.split(r'[^0-9,\.]+', a.reference)
                nums = [p.replace(',', '.') for p in parts if p]
                if len(nums) >= 2:
                    try:
                        min_ref, max_ref = float(nums[0]), float(nums[1])
                    except ValueError:
                        pass

            # выбираем эмодзи: 🟢 если в норме, 🔴 если вне
            if res_num is not None and min_ref is not None and max_ref is not None:
                emoji = '🟢' if min_ref <= res_num <= max_ref else '🔴'
            else:
                emoji = ''

            text += (
                f"📅 {dt}: {emoji}{a.result or '—'} {a.units or ''} "
                f"(Референс: {a.reference or '—'})\n"
            )
        await callback.message.answer(text)
    await callback.answer()

# 7. Отмена просмотра
@dp.callback_query(F.data == "cancel_view" or F.data == "show_menu")
async def cancel_view(callback: CallbackQuery):
    await callback.message.answer("Просмотр анализов отменён.")
    await callback.answer()
    
# --------------- Удаление анализов -----------------
class DeleteFlow(StatesGroup):
    waiting_for_group     = State()
    waiting_for_name      = State()
    waiting_for_analysis  = State()
    confirm_delete        = State()

@dp.message(F.text == "❌ Удалить анализ")
async def start_delete_analysis(message: Message, state: FSMContext):
    # Шаг 1: список групп
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.group_name)
            .where(Analysis.telegram_id == message.from_user.id)
            .distinct()
        )
        groups = [r[0] for r in res.all()]

    if not groups:
        await message.answer("У вас ещё нет ни одного анализа для удаления.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"del_group|{g}")]
            for g in groups
        ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="del_cancel")]]
    )
    await message.answer("Выберите группу анализа для удаления:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_group)

# Отмена на первом шаге — выход из потока
@dp.callback_query(DeleteFlow.waiting_for_group, F.data == "del_cancel")
async def cancel_delete_group(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Удаление отменено.")
    await state.clear()
    await callback.answer()

@dp.callback_query(DeleteFlow.waiting_for_group, F.data.startswith("del_group|"))
async def choose_delete_group(callback: CallbackQuery, state: FSMContext):
    group = callback.data.split("|", 1)[1]
    await state.update_data(group=group)

    # Шаг 2: список названий в группе
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.name)
            .where(
                Analysis.telegram_id == callback.from_user.id,
                Analysis.group_name == group
            )
            .distinct()
        )
        names = [r[0] for r in res.all()]

    if not names:
        await callback.message.edit_text("В этой группе нет анализов.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"del_name|{n}")]
            for n in names
        ] + [[InlineKeyboardButton(text="◀️ Назад", callback_data="del_back")]]
    )
    await callback.message.edit_text("Выберите название анализа:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_name)
    await callback.answer()

# «Назад» к выбору группы
@dp.callback_query(DeleteFlow.waiting_for_name, F.data == "del_back")
async def back_to_group(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.group_name)
            .where(Analysis.telegram_id == callback.from_user.id)
            .distinct()
        )
        groups = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=g, callback_data=f"del_group|{g}")]
            for g in groups
        ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="del_cancel")]]
    )
    await callback.message.edit_text("Выберите группу анализа для удаления:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_group)
    await callback.answer()

@dp.callback_query(DeleteFlow.waiting_for_name, F.data.startswith("del_name|"))
async def choose_delete_name(callback: CallbackQuery, state: FSMContext):
    name = callback.data.split("|", 1)[1]
    await state.update_data(name=name)

    # Шаг 3: список конкретных записей
    async with async_session() as session:
        res = await session.execute(
            select(Analysis)
            .where(
                Analysis.telegram_id == callback.from_user.id,
                Analysis.name == name
            )
            .order_by(desc(Analysis.date))
        )
        analyses = res.scalars().all()

    if not analyses:
        await callback.message.edit_text("Нет записей для этого анализа.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{a.date.strftime('%d.%m.%Y')}: {a.result or '—'} {a.units or ''}",
                callback_data=f"del_select|{a.id}"
            )]
            for a in analyses
        ] + [[InlineKeyboardButton(text="◀️ Назад", callback_data="del_back")]]
    )
    await callback.message.edit_text(
        f"Вы выбрали «{name}». Выберите запись для удаления:",
        reply_markup=kb
    )
    await state.set_state(DeleteFlow.waiting_for_analysis)
    await callback.answer()

# «Назад» к выбору названия анализа
@dp.callback_query(DeleteFlow.waiting_for_analysis, F.data == "del_back")
async def back_to_name(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    group = data.get("group")
    async with async_session() as session:
        res = await session.execute(
            select(Analysis.name)
            .where(
                Analysis.telegram_id == callback.from_user.id,
                Analysis.group_name == group
            )
            .distinct()
        )
        names = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"del_name|{n}")]
            for n in names
        ] + [[InlineKeyboardButton(text="◀️ Назад", callback_data="del_back")]]
    )
    await callback.message.edit_text("Выберите название анализа:", reply_markup=kb)
    await state.set_state(DeleteFlow.waiting_for_name)
    await callback.answer()

@dp.callback_query(DeleteFlow.waiting_for_analysis, F.data.startswith("del_select|"))
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    analysis_id = int(callback.data.split("|", 1)[1])
    async with async_session() as session:
        analysis = await session.get(Analysis, analysis_id)

    if not analysis:
        await callback.message.edit_text("Запись не найдена.")
        await state.clear()
        return

    await state.update_data(analysis_id=analysis_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[  
            InlineKeyboardButton(text="✅ Да", callback_data=f"del_confirm|{analysis_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="del_cancel")
        ]]
    )
    await callback.message.edit_text(
        f"Удалить анализ «{analysis.name}» от {analysis.date.strftime('%d.%m.%Y')}?",
        reply_markup=kb
    )
    await state.set_state(DeleteFlow.confirm_delete)
    await callback.answer()

@dp.callback_query(DeleteFlow.confirm_delete, F.data.startswith("del_confirm|"))
async def process_delete_confirm(callback: CallbackQuery, state: FSMContext):
    analysis_id = int(callback.data.split("|", 1)[1])
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(Analysis).where(Analysis.id == analysis_id))

    await callback.message.edit_text("✅ Анализ успешно удалён.")
    await state.clear()
    await callback.answer()
#------------------------------------------------------------------------------------------------------------------#
                                #Рекомендации#
                                
@dp.message(F.text == "📊 Рекомендации")
async def show_recommendation_categories(message: Message):
    async with async_session() as session:
        res = await session.execute(
            select(Recommendation.category)
            .where(Recommendation.telegram_id == message.from_user.id)
            .distinct()
        )
        categories = [r[0] for r in res.all()]

    if not categories:
        await message.answer("У вас пока нет рекомендаций.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cat, callback_data=f"rec_cat|{cat}")]
            for cat in categories
        ]
    )
    await message.answer("Выберите категорию рекомендаций:", reply_markup=kb)

# Step 2: Show all recommendations in selected category
@dp.callback_query(F.data.startswith("rec_cat|"))
async def show_recommendations(callback: CallbackQuery):
    category = callback.data.split("|", 1)[1]
    async with async_session() as session:
        res = await session.execute(
            select(Recommendation)
            .where(
                Recommendation.telegram_id == callback.from_user.id,
                Recommendation.category == category
            )
            .order_by(Recommendation.created_at)
        )
        recs = res.scalars().all()

    if not recs:
        await callback.answer("Нет рекомендаций в этой категории.", show_alert=True)
        return

    text_lines = [f"<b>📊 Рекомендации — {category}:</b>\n"]
    for idx, rec in enumerate(recs, 1):
        created = rec.created_at.strftime("%d.%m.%Y")
        text_lines.append(f"{idx}. {rec.text} <i>({created})</i>")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="rec_back")
        ]]
    )
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

# Step 3: Back to category list
@dp.callback_query(F.data == "rec_back")
async def back_to_categories(callback: CallbackQuery):
    async with async_session() as session:
        res = await session.execute(
            select(Recommendation.category)
            .where(Recommendation.telegram_id == callback.from_user.id)
            .distinct()
        )
        categories = [r[0] for r in res.all()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cat, callback_data=f"rec_cat|{cat}")]
            for cat in categories
        ]
    )
    await callback.message.edit_text(
        "Выберите категорию рекомендаций:",
        reply_markup=kb
    )
    await callback.answer()
#------------------------------------------------------------------------------------------------------------------#
                                #Назначения врача#        

class AppointmentFlow(StatesGroup):
    date = State()
    doctor = State()
    recommendation = State()
    next_action = State()

@dp.message(F.text == "💊 Назначения врачей")
async def analyses_menu_handler(message: Message):
    await message.answer("Выберите действие с Назначениями врачей:", reply_markup=doctor_keyboard)

# --------------- Добавить назначение -----------------
# Запуск потока ввода
@dp.message(F.text == "➕ Добавить назначение")
async def start_appointments(message: Message, state: FSMContext):
    await message.answer("Введите дату приёма в формате ДД.ММ.ГГГГ:")
    await state.set_state(AppointmentFlow.date)

# Обработка даты
@dp.message(AppointmentFlow.date)
async def process_date(message: Message, state: FSMContext):
    try:
        appt_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат. Введите дату как ДД.MM.ГГГГ:")
        return

    await state.update_data(appointment_date=appt_date)
    await message.answer("Введите специальность врача:")
    await state.set_state(AppointmentFlow.doctor)

# Обработка врача
@dp.message(AppointmentFlow.doctor)
async def process_doctor(message: Message, state: FSMContext):
    await state.update_data(doctor=message.text.strip())
    await message.answer("Введите текст назначения от этого врача:")
    await state.set_state(AppointmentFlow.recommendation)

# Обработка одной рекомендации
@dp.message(AppointmentFlow.recommendation)
async def process_recommendation(message: Message, state: FSMContext):
    data = await state.get_data()
    appt = DoctorAppointment(
        telegram_id=message.from_user.id,
        appointment_date=data["appointment_date"],
        doctor=data["doctor"],
        recommendation=message.text.strip()
    )
    async with async_session() as session:
        async with session.begin():
            session.add(appt)

    # Предлагаем, что делать дальше
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ Ещё от этого врача", callback_data="appt_add_same"),
        InlineKeyboardButton(text="👩‍⚕️ Другой врач", callback_data="appt_add_new"),
        InlineKeyboardButton(text="✅ Готово", callback_data="appt_finish"),
    ]])
    await message.answer("Запись сохранена. Что дальше?", reply_markup=kb)
    await state.set_state(AppointmentFlow.next_action)

# Добавить ещё рекомендацию от того же врача
@dp.callback_query(AppointmentFlow.next_action, F.data == "appt_add_same")
async def add_more_same(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("Введите ещё одно назначение для этого врача:")
    await state.set_state(AppointmentFlow.recommendation)
    await callback.answer()

# Перейти к вводу другого врача
@dp.callback_query(AppointmentFlow.next_action, F.data == "appt_add_new")
async def add_new_doctor(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("Введите специальность или имя следующего врача:")
    await state.set_state(AppointmentFlow.doctor)
    await callback.answer()

# Завершить ввод назначений
@dp.callback_query(AppointmentFlow.next_action, F.data == "appt_finish")
async def finish_appointments(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("✅ Все назначения сохранены.")
    await state.clear()
    await callback.answer()
    
# --------------- Посмотреть назначение -----------------
@dp.message(F.text == "📋 Посмотреть назначения")
async def view_doctor_appointments(message: types.Message):
    telegram_id = message.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(DoctorAppointment.doctor).where(DoctorAppointment.telegram_id == telegram_id)
        )
        doctors = list(set(row[0] for row in result.fetchall()))

    if not doctors:
        await message.answer("У вас пока нет назначений.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=doc, callback_data=f"view_appt_{doc}")]
            for doc in doctors
        ]
    )
    await message.answer("Выберите врача, чтобы посмотреть назначения:", reply_markup=keyboard)
    
@dp.callback_query(F.data.startswith("view_appt_"))
async def show_appointments_by_doctor(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    doctor = callback.data.removeprefix("view_appt_")

    async with async_session() as session:
        result = await session.execute(
            select(DoctorAppointment).where(
                DoctorAppointment.telegram_id == telegram_id,
                DoctorAppointment.doctor == doctor
            ).order_by(DoctorAppointment.appointment_date.desc())
        )
        appointments = result.scalars().all()

    if not appointments:
        await callback.message.answer("Назначений от этого врача не найдено.")
        await callback.answer()
        return

    text = f"📋 Назначения от врача: <b>{doctor}</b>\n\n"
    for appt in appointments:
        date = appt.appointment_date.strftime("%d.%m.%Y")
        text += f"🗓 <b>{date}</b>\n📝 {appt.recommendation}\n\n"

    await callback.message.answer(text)
    await callback.answer()

# --------------- Редактировать назначение -----------------

@dp.message(F.text == "✏️ Редактировать назначения")
async def choose_doctor_to_edit(callback: types.Message):
    telegram_id = callback.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(DoctorAppointment.doctor).where(DoctorAppointment.telegram_id == telegram_id)
        )
        doctors = list(set(row[0] for row in result.fetchall()))

    if not doctors:
        await callback.answer("У вас пока нет назначений.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=doc, callback_data=f"edit_doc_{doc}")]
            for doc in doctors
        ]
    )
    await callback.answer("Выберите врача для редактирования назначения:", reply_markup=keyboard)

# Обработчик выбора врача для редактирования
@dp.callback_query(F.data.startswith("edit_doc_"))
async def choose_appointment_to_edit(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    doctor = callback.data.removeprefix("edit_doc_")

    async with async_session() as session:
        result = await session.execute(
            select(DoctorAppointment).where(
                DoctorAppointment.telegram_id == telegram_id,
                DoctorAppointment.doctor == doctor
            ).order_by(DoctorAppointment.appointment_date.desc())
        )
        appointments = result.scalars().all()

    if not appointments:
        await callback.message.edit_text("У этого врача нет назначений.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{appt.appointment_date.strftime('%d.%m.%Y')} {appt.recommendation[:25]}{'...' if len(appt.recommendation) > 25 else ''}",
                callback_data=f"edit_appt_{appt.id}"
            )]
            for appt in appointments
        ]
    )
    await callback.message.edit_text("Выберите назначение для редактирования:", reply_markup=keyboard)

# Обработчик выбора назначения для редактирования
@dp.callback_query(F.data.startswith("edit_appt_"))
async def ask_for_new_text(callback: types.CallbackQuery, state: FSMContext):
    appt_id = int(callback.data.removeprefix("edit_appt_"))
    await state.update_data(appt_id=appt_id)

    # Кнопка для отмены редактирования
    cancel_button = InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])

    await callback.message.edit_text("Введите новый текст назначения:", reply_markup=keyboard)
    await state.set_state(EditAppointmentState.waiting_for_text)

# Состояние для редактирования текста назначения
class EditAppointmentState(StatesGroup):
    waiting_for_text = State()

# Обработчик ввода нового текста для назначения
@dp.message(EditAppointmentState.waiting_for_text)
async def save_edited_text(message: types.Message, state: FSMContext):
    new_text = message.text
    data = await state.get_data()
    appt_id = data['appt_id']

    async with async_session() as session:
        result = await session.execute(select(DoctorAppointment).where(DoctorAppointment.id == appt_id))
        appt = result.scalar_one_or_none()

        if not appt:
            await message.answer("Ошибка: назначение не найдено.")
            await state.clear()
            return

        appt.recommendation = new_text
        await session.commit()

    await message.answer("Текст назначения успешно обновлён ✅")
    await state.clear()

# Обработчик для отмены редактирования
@dp.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Редактирование отменено.")
    await state.clear()
    
# --------------- Редактировать назначение -----------------

# Обработчик команды "Удалить назначения"
@dp.message(F.text == "❌ Удалить назначения")
async def choose_doctor_to_delete(callback: types.Message):
    telegram_id = callback.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(DoctorAppointment.doctor).where(DoctorAppointment.telegram_id == telegram_id)
        )
        doctors = list(set(row[0] for row in result.fetchall()))  # Уникальные врачи

    if not doctors:
        await callback.answer("У вас пока нет назначений.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=doc, callback_data=f"delete_doc_{doc}")]
            for doc in doctors
        ]
    )

    # Добавляем кнопку отмены
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_delete")])

    await callback.answer("Выберите врача для удаления назначения:", reply_markup=keyboard)


# Обработчик выбора врача для удаления
@dp.callback_query(F.data.startswith("delete_doc_"))
async def choose_appointment_to_delete(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    doctor = callback.data.removeprefix("delete_doc_")

    async with async_session() as session:
        result = await session.execute(
            select(DoctorAppointment).where(
                DoctorAppointment.telegram_id == telegram_id,
                DoctorAppointment.doctor == doctor
            ).order_by(DoctorAppointment.appointment_date.desc())
        )
        appointments = result.scalars().all()

    if not appointments:
        await callback.message.edit_text("У этого врача нет назначений.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{appt.appointment_date.strftime('%d.%m.%Y')} {appt.recommendation[:25]}{'...' if len(appt.recommendation) > 25 else ''}",
                callback_data=f"delete_appt_{appt.id}"
            )]
            for appt in appointments
        ]
    )

    # Добавляем кнопку отмены с использованием append
    cancel_button = InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_delete")
    keyboard.inline_keyboard.append([cancel_button])  # исправлено на append

    await callback.message.edit_text("Выберите назначение для удаления:", reply_markup=keyboard)


# Обработчик выбора назначения для удаления
@dp.callback_query(F.data.startswith("delete_appt_"))
async def confirm_delete_appointment(callback: types.CallbackQuery, state: FSMContext):
    appt_id = int(callback.data.removeprefix("delete_appt_"))
    await state.update_data(appt_id=appt_id)

    # Кнопки для подтверждения удаления
    confirm_button = InlineKeyboardButton(text="✅ Да", callback_data="confirm_delete_yes")
    cancel_button = InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[confirm_button, cancel_button]])

    await callback.message.edit_text("Вы точно хотите удалить это назначение?", reply_markup=keyboard)

# Обработчик подтверждения удаления
@dp.callback_query(F.data == "confirm_delete_yes")
async def delete_appointment(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    appt_id = data['appt_id']

    async with async_session() as session:
        result = await session.execute(select(DoctorAppointment).where(DoctorAppointment.id == appt_id))
        appt = result.scalar_one_or_none()

        if not appt:
            await callback.message.edit_text("Ошибка: назначение не найдено.")
            await state.clear()
            return

        # Удаляем назначение
        await session.delete(appt)
        await session.commit()

    await callback.message.edit_text("Назначение успешно удалено ✅")
    await state.clear()

# Обработчик для отмены удаления
@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Операция удаления отменена.")
    await state.clear()
    
    
#------------------------------------------------------------------------------------------------------------------#
                                #Обследования#

UPLOAD_DIR = "uploaded_files"  # Папка для сохранения файлов

# Создание директории, если её нет
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

async def save_examination_file(message: Message):
    try:
        # Получаем файл с помощью file_id
        file_info = await bot.get_file(message.document.file_id)
        file_name = message.document.file_name

        # Путь для сохранения файла
        file_path = os.path.join(UPLOAD_DIR, file_name)

        # Загружаем файл на диск
        await bot.download_file(file_info.file_path, file_path)

        return file_path  # Возвращаем путь к файлу

    except TelegramAPIError as e:
        print(f"Ошибка при получении файла: {e}")
        return None

@dp.message(F.text == "🩻 Обследования")
async def examinations_menu_handler(message: types.Message):
    await message.answer("Выберите действие с обследованиями:", reply_markup=examination_keyboard)

@dp.message(F.text == "➕ Добавить обследование")
async def add_examination(message: types.Message, state: FSMContext):
    await message.answer("🩻 Введите название обследования:")
    await state.set_state("examination_name")

@dp.message(StateFilter("examination_name"))
async def get_examination_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📅 Введите дату обследования (в формате ДД.ММ.ГГГГ):")
    await state.set_state("examination_date")

@dp.message(StateFilter("examination_date"))
async def get_examination_date(message: types.Message, state: FSMContext):
    try:
        date = datetime.strptime(message.text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("❗ Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ):")
        return

    await state.update_data(date=date)
    await message.answer("📝 Введите краткое описание обследования:")
    await state.set_state("examination_description")

@dp.message(StateFilter("examination_description"))
async def get_examination_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("📎 Прикрепите файл (до 50 МБ) или нажмите /skip, если файл не нужен:")
    await state.set_state("examination_file")

@dp.message(StateFilter("examination_file"), F.document)
async def get_examination_file(message: types.Message, state: FSMContext):
    file = message.document

    if file.file_size > 50 * 1024 * 1024:
        await message.answer("❗ Файл слишком большой. Пожалуйста, прикрепите файл размером до 50 МБ.")
        return

    # Сохраняем файл и получаем путь
    file_path = await save_examination_file(message)

    await state.update_data(file=file_path)
    await save_examination(message, state)

@dp.message(StateFilter("examination_file"), Command("skip"))
async def skip_examination_file(message: types.Message, state: FSMContext):
    await state.update_data(file=None)
    await save_examination(message, state)

async def save_examination(message: types.Message, state: FSMContext):
    data = await state.get_data()

    # Создаем новый объект обследования
    new_exam = InstrumentalExamination(
        telegram_id=message.from_user.id,
        name=data["name"],
        examination_date=data["date"],
        description=data["description"],
        file_path=data.get("file"),  # file_path теперь хранит путь к файлу
        created_at=datetime.utcnow()
    )

    # Сохраняем в базе данных
    async with async_session() as session:
        session.add(new_exam)
        await session.commit()

    await message.answer("✅ Обследование успешно добавлено.")
    await state.clear()
# --------------- Посмотреть обследования -----------------
@dp.message(F.text == "📋 Посмотреть обследования")
async def view_examinations(message: types.Message):
    await message.answer("🔄 Функция просмотра обследований в разработке.")

# --------------- Редактировать обследование -----------------
@dp.message(F.text == "✏️ Редактировать обследования")
async def edit_examination(message: types.Message):
    await message.answer("🔄 Функция редактирования обследований в разработке.")

# --------------- Удалить обследование -----------------
@dp.message(F.text == "❌ Удалить обследования")
async def delete_examination(message: types.Message):
    await message.answer("🔄 Функция удаления обследований в разработке.")         
#------------------------------------------------------------------------------------------------------------------#
# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
