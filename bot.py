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
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os
import asyncio
from db import async_session, UserData, Analysis
from sqlalchemy import select, delete, func


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

from sqlalchemy import select
class AddAnalysis(StatesGroup):
    name = State()
    reference = State()
    units = State()
    result = State()
    date = State()
    
@dp.message(F.text == "🧪 Анализы")
async def analyses_menu_handler(message: Message):
    await message.answer("Выберите действие с анализами:", reply_markup=analysis_keyboard)

@dp.message(F.text == "➕ Добавить анализ")
async def start_add_analysis(message: Message, state: FSMContext):
    await message.answer("Введите название анализа:")
    await state.set_state(AddAnalysis.name)
@dp.message(AddAnalysis.name)
async def get_analysis_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите референсные значения (например, 120–160):")
    await state.set_state(AddAnalysis.reference)

@dp.message(AddAnalysis.reference)
async def get_analysis_reference(message: Message, state: FSMContext):
    await state.update_data(reference=message.text)
    await message.answer("Введите единицы измерения (например, г/л):")
    await state.set_state(AddAnalysis.units)

@dp.message(AddAnalysis.units)
async def get_analysis_units(message: Message, state: FSMContext):
    await state.update_data(units=message.text)
    await message.answer("Введите результат анализа:")
    await state.set_state(AddAnalysis.result)

@dp.message(AddAnalysis.result)
async def get_analysis_result(message: Message, state: FSMContext):
    await state.update_data(result=message.text)
    await message.answer("Введите дату сдачи анализа (в формате ГГГГ-ММ-ДД):")
    await state.set_state(AddAnalysis.date)

@dp.message(AddAnalysis.date)
async def get_analysis_date(message: Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        date_value = message.text.strip()
        
        # Простая проверка формата даты
        from datetime import datetime
        date_obj = datetime.strptime(date_value, "%Y-%m-%d").date()

        async with async_session() as session:
            async with session.begin():
                new_analysis = Analysis(
                    telegram_id=message.from_user.id,
                    name=user_data["name"],
                    reference=user_data["reference"],
                    units=user_data["units"],
                    result=user_data["result"],
                    date=date_obj
                )
                session.add(new_analysis)

        await message.answer("✅ Анализ успешно добавлен!", reply_markup=analysis_keyboard)
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}. Повторите ввод даты в формате ГГГГ-ММ-ДД.")


@dp.message(F.text == "📋 Посмотреть анализы")
async def show_analyses_handler(message: Message):
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Analysis).where(Analysis.telegram_id == message.from_user.id)
            )
            analyses = result.scalars().all()

    if not analyses:
        await message.answer(
            "📋 У вас ещё нет ни одного анализа.",
            reply_markup=main_keyboard
        )
        return

    text = "<b>Ваши анализы:</b>\n\n"
    for a in analyses:
        date_str = a.date.isoformat() if a.date else "—"
        text += (
            f"📅 {date_str}: <b>{a.name}</b> — {a.result or '—'} {a.units or ''} "
            f"(Референсные значения: {a.reference or '—'})\n"
        )

    await message.answer(text, reply_markup=analysis_keyboard)

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

    # закрываем «ждущую» анимацию и редактируем сообщение
    await callback_query.answer("Удаляю…")
    await callback_query.message.edit_text(
        f"✅ Анализ «{analysis.name}» от {analysis.date.strftime('%Y-%m-%d')} удалён."
    )
    await state.clear()

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
