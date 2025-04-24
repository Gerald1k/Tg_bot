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
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os
import asyncio
from db import async_session, UserData, Analysis, AnalyzesMem
from sqlalchemy import select, delete, func, desc
from datetime import datetime, date, timedelta
import dateparser
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
        [KeyboardButton(text="❌ Удалить пользователя")]
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
    async with async_session() as session:
        q = (
            select(Analysis)
            .where(Analysis.telegram_id == callback.from_user.id)
            .order_by(Analysis.name, desc(Analysis.date))
        )
        res = await session.execute(q)
        analyses = res.scalars().all()

    grouped = {}
    for a in analyses:
        grouped.setdefault(a.name, []).append(a)

    table_data = [[
        'Анализ', 'Последний результат (дата)',
        'Предыдущий результат (дата)', 'Референс', 'Ед. изм.'
    ]]
    for name, items in grouped.items():
        last = items[0]
        prev = items[1] if len(items) > 1 else None
        table_data.append([
            name,
            f"{last.result} ({last.date.strftime('%d.%m.%Y')})",
            f"{prev.result} ({prev.date.strftime('%d.%m.%Y')})" if prev else '—',
            last.reference or '—',
            last.units or '—'
        ])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('FONTNAME',    (0,0), (-1,-1), 'ArialUnicode'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)
    ]))
    doc.build([table])
    buffer.seek(0)

    # 1) пишем PDF во временный файл на диске
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
        tf.write(buffer.read())
        temp_path = tf.name

    # 2) отправляем его через FSInputFile
    file = FSInputFile(temp_path, filename='all_analyses.pdf')
    await callback.message.answer_document(file)
    await callback.answer()

    # 3) удаляем временный файл
    os.remove(temp_path)

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
class DeleteAnalysis(StatesGroup):
    name = State()
    choosing = State()

@dp.message(F.text == "❌ Удалить анализ")
async def start_delete_analysis(message: Message, state: FSMContext):
    await message.answer("Введите название анализа, который вы хотите удалить:")
    await state.set_state(DeleteAnalysis.name)

@dp.message(DeleteAnalysis.name)
async def delete_analysis_by_name(message: Message, state: FSMContext):
    analysis_name = message.text.strip()

    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Analysis)
                .where(
                    func.lower(Analysis.name) == analysis_name.lower(),
                    Analysis.telegram_id == message.from_user.id
                )
            )
            analyses = result.scalars().all()

    if not analyses:
        await message.answer("❌ Анализ с таким названием не найден.")
        await state.clear()
        return

    # Если ровно один — удаляем сразу
    if len(analyses) == 1:
        async with async_session() as session:
            async with session.begin():
                await session.delete(analyses[0])
        await message.answer(f"✅ Анализ «{analyses[0].name}» удалён.")
        await state.clear()
        return

    # Если несколько — строим кнопки
    builder = InlineKeyboardBuilder()
    for analysis in analyses:
        btn_text = f"{analysis.name} — {analysis.date.strftime('%Y-%m-%d')}"
        builder.button(
            text=btn_text,
            callback_data=f"del_analysis:{analysis.id}"
        )
    builder.adjust(1)  # 1 кнопка в ряду

    await message.answer(
        "Найдено несколько анализов. Выберите, какой удалить:", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(DeleteAnalysis.choosing)

@dp.callback_query(DeleteAnalysis.choosing, lambda cb: cb.data.startswith("del_analysis:"))
async def process_delete_analysis_cb(callback_query: CallbackQuery, state: FSMContext):
    # cb.data = "del_analysis:<id>"
    analysis_id = int(callback_query.data.split(":", 1)[1])

    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Analysis).where(Analysis.id == analysis_id)
            )
            analysis = result.scalar_one_or_none()
            if analysis:
                await session.delete(analysis)

    await callback_query.message.edit_text(
        f"✅ Анализ «{analysis.name}» от {analysis.date.strftime('%Y-%m-%d')} удалён."
    )
    await state.clear()

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
