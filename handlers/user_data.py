from aiogram import Router, F
import html
from keyboards.main_menu import main_keyboard, fill_data_keyboard, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import(
    Message,
    CallbackQuery
    )
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select, delete

from states.data_states import DataStates, EditStates, DeleteStates 
from db import async_session, UserData
router = Router() 

# Главное меню → "Данные пользователя"
@router.message(F.text == "📝 Данные пользователя")
async def fill_data_handler(message: Message):
    await message.answer(
        "🔒 В этом разделе вы можете ввести свои данные, отредактировать их или удалить, если это необходимо.\n\n"
        "Выберите действие, которое хотите выполнить:",
        reply_markup=fill_data_keyboard
    )

# Начало FSM: ввод ФИО
@router.message(F.text == "🖊 Ввести данные")
async def enter_data_handler(message: Message, state: FSMContext):
    await state.set_state(DataStates.fio)
    await message.answer("Введите ваше ФИО:")

# Обработка ФИО → выбор цели
@router.message(StateFilter(DataStates.fio))
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
@router.callback_query(StateFilter(DataStates.goal), F.data.startswith("goal:"))
async def process_goal_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    goal = query.data.split(":", 1)[1]
    await state.update_data(goal=goal)
    await state.set_state(DataStates.sport)
    await query.message.edit_reply_markup()
    await query.message.answer("Занимаетесь ли вы каким-либо спортом? Если да, укажите вид и частоту занятий:")

# Обработка спорта → рост
@router.message(StateFilter(DataStates.sport))
async def process_sport(message: Message, state: FSMContext):
    await state.update_data(sport=message.text)
    await state.set_state(DataStates.height)
    await message.answer("Введите ваш рост (в сантиметрах):")

@router.message(StateFilter(DataStates.height))
async def process_height(message: Message, state: FSMContext):
    try:
        height = float(message.text)
        if height <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение роста в сантиметрах (например, 170).")
        return

    await state.update_data(height=height)
    await state.set_state(DataStates.weight)
    await message.answer("Введите ваш вес (в килограммах):")

# Обработка веса → курение
@router.message(StateFilter(DataStates.weight))
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = float(message.text)
        if weight <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное значение веса в килограммах (например, 70).")
        return

    await state.update_data(weight=weight)
    kb = InlineKeyboardMarkup(inline_keyboard=[  # Кнопки для курения
        [InlineKeyboardButton(text="Да", callback_data="smoking:Да")],
        [InlineKeyboardButton(text="Нет", callback_data="smoking:Нет")],
    ])
    await state.set_state(DataStates.smoking)
    await message.answer("Курите ли вы?", reply_markup=kb)

# Обработка курения → алкоголь
@router.callback_query(StateFilter(DataStates.smoking), F.data.startswith("smoking:"))
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
@router.callback_query(StateFilter(DataStates.alcohol), F.data.startswith("alcohol:"))
async def process_alcohol_cb(query: CallbackQuery, state: FSMContext):
    await query.answer()
    alcohol = query.data.split(":", 1)[1]
    await state.update_data(alcohol=alcohol)
    await query.message.edit_reply_markup()
    await state.set_state(DataStates.chronic)
    await query.message.answer("Есть ли у вас хронические болезни? Перечислите:")

# Обработка хронических болезней → наследственность
@router.message(StateFilter(DataStates.chronic))
async def process_chronic(message: Message, state: FSMContext):
    await state.update_data(chronic=message.text)
    await state.set_state(DataStates.heredity)
    await message.answer("Наследственная предрасположенность (перечислите, если есть):")

# Обработка наследственности → клиника
@router.message(StateFilter(DataStates.heredity))
async def process_heredity(message: Message, state: FSMContext):
    await state.update_data(heredity=message.text)
    await state.set_state(DataStates.clinical)
    await message.answer("Клинические проявления (симптомы, жалобы):")

# Финальный шаг: сохранение и вывод
@router.message(StateFilter(DataStates.clinical))
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
    
#---------------------------------------------------------------------------------------------------------------------------------
# Остальные пункты меню  
@router.message(F.text == "👁️ Посмотреть текущие данные")
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
        f"👤 ФИО: {html.escape(user.full_name) or 'Не указано'}\n"
        f"🎯 Цель: {html.escape(user.goal) or 'Не указано'}\n"
        f"🏅 Спорт: {html.escape(user.sport) or 'Не указан'}\n"
        f"📏 Рост: {user.height or 'Не указан'} см\n"
        f"⚖️ Вес: {user.weight or 'Не указан'} кг\n"
        f"🚬 Курение: {html.escape(user.smoking) or 'Не указано'}\n"
        f"🍷 Алкоголь: {html.escape(user.alcohol) or 'Не указано'}\n"
        f"💉 Хронические болезни: {html.escape(user.diseases) or 'Не указано'}\n"
        f"🧬 Наследственная предрасположенность: {html.escape(user.heredity) or 'Не указано'}\n"
        f"🩺 Клинические проявления: {html.escape(user.symptoms) or 'Не указаны'}\n"
    )
    await message.answer(summary, reply_markup=fill_data_keyboard)
#---------------------------------------------------------------------------------------------------------------------------------
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
@router.message(F.text == "✏️ Редактировать данные")
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
@router.callback_query(StateFilter(EditStates.field), F.data.startswith("edit:"))
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
@router.callback_query(StateFilter(EditStates.value), F.data.startswith("edit_goal:"))
@router.callback_query(StateFilter(EditStates.value), F.data.startswith("edit_smoking:"))
@router.callback_query(StateFilter(EditStates.value), F.data.startswith("edit_alcohol:"))
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
@router.message(StateFilter(EditStates.value))
async def process_edit_text_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    new_value = message.text


     # Валидация для числовых полей
    if field == 'height':
        try:
            new_value = float(message.text)
            if new_value <= 0:
                await message.answer("Пожалуйста, введите положительное число для роста.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите корректное число для роста.")
            return

    if field == 'weight':
        try:
            new_value = float(message.text)
            if new_value <= 0:
                await message.answer("Пожалуйста, введите положительное число для веса.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите корректное число для веса.")
            return
    
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


#---------------------------------------------------------------------------------------------------------------------------------
@router.message(F.text == "❌ Удалить данные")
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
@router.message(StateFilter(DeleteStates.confirm))
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


@router.message(F.text == "⬅️ Назад")
async def back_to_main_menu(message: Message):
    await message.answer("🔙 Вы вернулись в главное меню. Выберите следующее действие.", reply_markup=main_keyboard)