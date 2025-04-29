from aiogram import Router, F, types
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.filters.command import Command
import os

from keyboards.main_menu import InlineKeyboardButton, InlineKeyboardMarkup, examination_keyboard
from states.examination_states import EditExamStates 
from db import  async_session, InstrumentalExamination


router = Router() 

UPLOAD_DIR = "uploaded_files"  # Папка для сохранения файлов

# Создание директории, если её нет
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

async def save_examination_file(message: Message):
    try:
        if not message.document:
            return None

        file_info = await message.bot.get_file(message.document.file_id)
        file_name = message.document.file_name

        # Генерируем уникальный путь
        file_path = get_unique_file_path(UPLOAD_DIR, file_name)

        # Сохраняем файл
        await message.bot.download(message.document.file_id, destination=file_path)

        return file_path

    except TelegramAPIError as e:
        print(f"Ошибка при получении файла: {e}")
        return None
    
def get_unique_file_path(upload_dir: str, original_name: str) -> str:
    """Формирует уникальное имя файла, если такой файл уже есть"""
    base, extension = os.path.splitext(original_name)
    counter = 1
    new_name = original_name

    while os.path.exists(os.path.join(upload_dir, new_name)):
        new_name = f"{base}_{counter}{extension}"
        counter += 1

    return os.path.join(upload_dir, new_name)

@router.message(F.text == "🩻 Обследования")
async def examinations_menu_handler(message: types.Message):
    await message.answer("Выберите действие с обследованиями:", reply_markup=examination_keyboard)

@router.message(F.text == "➕ Добавить обследование")
async def add_examination(message: types.Message, state: FSMContext):
    await message.answer("🩻 Введите название обследования:")
    await state.set_state("examination_name")

@router.message(StateFilter("examination_name"))
async def get_examination_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📅 Введите дату обследования (в формате ДД.ММ.ГГГГ):")
    await state.set_state("examination_date")

@router.message(StateFilter("examination_date"))
async def get_examination_date(message: types.Message, state: FSMContext):
    try:
        date = datetime.strptime(message.text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("❗ Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ):")
        return

    await state.update_data(date=date)
    await message.answer("📝 Введите краткое описание обследования:")
    await state.set_state("examination_description")

@router.message(StateFilter("examination_description"))
async def get_examination_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("📎 Прикрепите файл (до 50 МБ) или нажмите /skip, если файл не нужен:")
    await state.set_state("examination_file")

@router.message(StateFilter("examination_file"), F.document)
async def get_examination_file(message: types.Message, state: FSMContext):
    file = message.document

    if file.file_size > 50 * 1024 * 1024:
        await message.answer("❗ Файл слишком большой. Пожалуйста, прикрепите файл размером до 50 МБ.")
        return

    # Сохраняем файл и получаем путь
    file_path = await save_examination_file(message)

    await state.update_data(file=file_path)
    await save_examination(message, state)

@router.message(StateFilter("examination_file"), Command("skip"))
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

# 1) Список обследований
@router.message(F.text == "📋 Посмотреть обследования")
async def view_examinations(message: types.Message):
    async with async_session() as session:
        result = await session.execute(
            select(InstrumentalExamination.id, InstrumentalExamination.name)
            .where(InstrumentalExamination.telegram_id == message.from_user.id)
            .distinct()
        )

        exams = result.all()  # список кортежей (id, name)

    if not exams:
        await message.answer("❗ Пока нет доступных обследований.")
        return

    # Кнопка для каждого обследования хранит в callback_data его ID
    rows = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=f"view_examination:{exam_id}"
            )
        ]
        for exam_id, name in exams
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer("Выберите обследование для просмотра:", reply_markup=keyboard)


# 2) Детали выбранного обследования
@router.callback_query(F.data.startswith("view_examination:"))
async def view_examination_details(callback_query: types.CallbackQuery):
    exam_id = int(callback_query.data.split(":", 1)[1])

    async with async_session() as session:
        result = await session.execute(
            select(InstrumentalExamination)
            .where(
                InstrumentalExamination.id == exam_id,
                InstrumentalExamination.telegram_id == callback_query.from_user.id
            )
)
        exam = result.scalar_one_or_none()

    if not exam:
        await callback_query.answer("❗ Обследование не найдено.", show_alert=True)
        return

    date_str = exam.examination_date.strftime("%d.%m.%Y")
    desc = exam.description or ""
    short_desc = (desc[:150] + "...") if len(desc) > 150 else desc

    # Формируем кнопки
    buttons = []
    if exam.file_path:
        buttons.append(
            InlineKeyboardButton(
                text="📎 Скачать файл",
                callback_data=f"download:{exam_id}"
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data="cancel"
        )
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[buttons])
    text = (
        f"🔍 <b>{exam.name}</b>\n"
        f"📅 Дата: {date_str}\n"
        f"📝 Описание: {short_desc}"
    )
    await callback_query.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback_query.answer()  # закрыть «часики»


# 3) Загрузка файла
@router.callback_query(F.data.startswith("download:"))
async def download_file(callback_query: types.CallbackQuery):
    exam_id = int(callback_query.data.split(":", 1)[1])

    async with async_session() as session:
        result = await session.execute(
            select(InstrumentalExamination.file_path).filter_by(id=exam_id)
        )
        file_path = result.scalar_one_or_none()

    if not file_path:
        await callback_query.answer("❗ Файл не найден в базе.", show_alert=True)
        return

    await callback_query.answer("📥 Загружаю файл...")

    try:
        document = FSInputFile(path=file_path)
        await callback_query.message.answer_document(document)
    except FileNotFoundError:
        await callback_query.message.answer("❗ Файл отсутствует на сервере.")
    except Exception:
        await callback_query.message.answer("❗ Не удалось отправить файл.")


# 4) Отмена/закрыть
@router.callback_query(F.data == "cancel")
async def cancel(callback_query: types.CallbackQuery):
    await callback_query.answer("❌ Операция отменена.", show_alert=False)
# --------------- Редактировать обследование -----------------


# 1) Запуск редактирования: показываем список обследований
@router.message(F.text == "✏️ Редактировать обследования")
async def edit_examination_start(message: types.Message):
    user_id = message.from_user.id
    async with async_session() as session:
        result = await session.execute(
            select(InstrumentalExamination.id, InstrumentalExamination.name)
            .filter_by(telegram_id=user_id)
            .order_by(InstrumentalExamination.examination_date.desc())
        )
        exams = result.all()

    if not exams:
        return await message.answer("❗ У вас нет ни одного обследования для редактирования.")

    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"edit_examination:{exam_id}")]
        for exam_id, name in exams
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer("Выберите обследование для редактирования:", reply_markup=kb)

# 2) Пользователь выбрал обследование — запрашиваем новое описание
@router.callback_query(F.data.startswith("edit_examination:"))
async def edit_examination_select(callback: types.CallbackQuery, state: FSMContext):
    exam_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        exam = await session.get(InstrumentalExamination, exam_id)
    if not exam or exam.telegram_id != callback.from_user.id:
        await callback.answer("❗ Обследование не найдено или доступ запрещён.", show_alert=True)
        return

    # Сохраняем старые данные в контекст
    await state.update_data(
        exam_id=exam_id,
        old_description=exam.description or "",
        old_file_path=exam.file_path
    )

    text = (
        f"📝 Текущее описание:\n\n"
        f"{exam.description or '(пусто)'}\n\n"
        "Введите новое описание или отправьте /skip, чтобы оставить без изменений."
    )
    await callback.message.answer(text)
    await state.set_state(EditExamStates.desc)
    await callback.answer()

# 3) Новый текст описания или /skip
@router.message(F.text, StateFilter(EditExamStates.desc))
async def edit_examination_desc(message: types.Message, state: FSMContext):
    if message.text.strip() == "/skip":
        await state.update_data(new_description=None)
    else:
        await state.update_data(new_description=message.text.strip())

    await message.answer("📎 Прикрепите новый файл или отправьте /skip, чтобы оставить старый.")
    await state.set_state(EditExamStates.file)

# 4a) Пользователь присылает новый файл
@router.message(StateFilter(EditExamStates.file), F.document)
async def edit_examination_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # Сохраняем новый файл
    new_path = await save_examination_file(message)
    await state.update_data(new_file_path=new_path)
    await _commit_edit(message, state)

# 4b) Пользователь пропускает замену файла
@router.message(StateFilter(EditExamStates.file), F.text == "/skip")
async def edit_examination_file_skip(message: types.Message, state: FSMContext):
    await state.update_data(new_file_path=None)
    await _commit_edit(message, state)

# Вспомогательная функция для сохранения изменений
async def _commit_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    exam_id       = data["exam_id"]
    new_desc      = data.get("new_description")
    new_file      = data.get("new_file_path")
    old_file      = data.get("old_file_path")

    async with async_session() as session:
        exam = await session.get(InstrumentalExamination, exam_id)

        if new_desc is not None:
            exam.description = new_desc

        if new_file is not None:
            # удаляем старый файл
            if old_file and os.path.exists(old_file):
                try:
                    os.remove(old_file)
                except OSError:
                    pass
            exam.file_path = new_file

        await session.commit()

    await message.answer("✅ Обследование успешно обновлено.")
    await state.clear()
# --------------- Удалить обследование -----------------
# 1) Показываем список обследований для выбора
@router.message(F.text == "❌ Удалить обследования")
async def delete_examination_start(message: types.Message):
    user_id = message.from_user.id
    async with async_session() as session:
        result = await session.execute(
            select(InstrumentalExamination.id, InstrumentalExamination.name)
            .filter_by(telegram_id=user_id)
            .order_by(InstrumentalExamination.examination_date.desc())
        )
        exams = result.all()

    if not exams:
        return await message.answer("❗ У вас нет ни одного обследования для удаления.")

    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"choose_examination_to_delete:{exam_id}")]
        for exam_id, name in exams
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer("Выберите обследование, которое хотите удалить:", reply_markup=kb)


# 2) Пользователь выбрал обследование — спрашиваем подтверждение
@router.callback_query(F.data.startswith("choose_examination_to_delete:"))
async def confirm_delete_examination(callback_query: types.CallbackQuery):
    exam_id = int(callback_query.data.split(":")[1])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{exam_id}"),
            InlineKeyboardButton(text="❌ Нет, отменить", callback_data="cancel_delete")
        ]
    ])

    await callback_query.message.answer("❗ Вы уверены, что хотите удалить это обследование?", reply_markup=kb)
    await callback_query.answer()


# 3) Пользователь подтвердил удаление
@router.callback_query(F.data.startswith("confirm_delete:"))
async def delete_examination(callback_query: types.CallbackQuery):
    exam_id = int(callback_query.data.split(":")[1])

    async with async_session() as session:
        exam = await session.get(InstrumentalExamination, exam_id)
        if not exam or exam.telegram_id != callback_query.from_user.id:
            await callback_query.answer("❗ Обследование не найдено или доступ запрещён.", show_alert=True)
            return

        file_path = exam.file_path

        await session.delete(exam)
        await session.commit()

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    await callback_query.message.answer("✅ Обследование успешно удалено.")
    await callback_query.answer()


# 4) Пользователь отменил удаление
@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback_query: types.CallbackQuery):
    await callback_query.message.answer("❌ Удаление отменено.")
    await callback_query.answer()