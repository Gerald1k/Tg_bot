from aiogram import Router, F, types
from aiogram.types import(
    Message,
    CallbackQuery
    )
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime

from keyboards.main_menu import InlineKeyboardButton, InlineKeyboardMarkup, doctor_keyboard
from states.appointment_states import AppointmentFlow, EditAppointmentState
from db import DoctorAppointment, async_session


router = Router() 

@router.message(F.text == "💊 Назначения врачей")
async def analyses_menu_handler(message: Message):
    await message.answer("Выберите действие с Назначениями врачей:", reply_markup=doctor_keyboard)

# --------------- Добавить назначение -----------------
# Запуск потока ввода
@router.message(F.text == "➕ Добавить назначение")
async def start_appointments(message: Message, state: FSMContext):
    await message.answer("Введите дату приёма в формате ДД.ММ.ГГГГ:")
    await state.set_state(AppointmentFlow.date)

# Обработка даты
@router.message(AppointmentFlow.date)
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
@router.message(AppointmentFlow.doctor)
async def process_doctor(message: Message, state: FSMContext):
    await state.update_data(doctor=message.text.strip())
    await message.answer("Введите текст назначения от этого врача:")
    await state.set_state(AppointmentFlow.recommendation)

# Обработка одной рекомендации
@router.message(AppointmentFlow.recommendation)
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
@router.callback_query(AppointmentFlow.next_action, F.data == "appt_add_same")
async def add_more_same(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("Введите ещё одно назначение для этого врача:")
    await state.set_state(AppointmentFlow.recommendation)
    await callback.answer()

# Перейти к вводу другого врача
@router.callback_query(AppointmentFlow.next_action, F.data == "appt_add_new")
async def add_new_doctor(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("Введите специальность или имя следующего врача:")
    await state.set_state(AppointmentFlow.doctor)
    await callback.answer()

# Завершить ввод назначений
@router.callback_query(AppointmentFlow.next_action, F.data == "appt_finish")
async def finish_appointments(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("✅ Все назначения сохранены.")
    await state.clear()
    await callback.answer()
    
# --------------- Посмотреть назначение -----------------
@router.message(F.text == "📋 Посмотреть назначения")
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
    
@router.callback_query(F.data.startswith("view_appt_"))
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

@router.message(F.text == "✏️ Редактировать назначения")
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
@router.callback_query(F.data.startswith("edit_doc_"))
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
@router.callback_query(F.data.startswith("edit_appt_"))
async def ask_for_new_text(callback: types.CallbackQuery, state: FSMContext):
    appt_id = int(callback.data.removeprefix("edit_appt_"))
    await state.update_data(appt_id=appt_id)

    # Кнопка для отмены редактирования
    cancel_button = InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])

    await callback.message.edit_text("Введите новый текст назначения:", reply_markup=keyboard)
    await state.set_state(EditAppointmentState.waiting_for_text)

# Обработчик ввода нового текста для назначения
@router.message(EditAppointmentState.waiting_for_text)
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
@router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Редактирование отменено.")
    await state.clear()
    
# --------------- Редактировать назначение -----------------

# Обработчик команды "Удалить назначения"
@router.message(F.text == "❌ Удалить назначения")
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
@router.callback_query(F.data.startswith("delete_doc_"))
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
@router.callback_query(F.data.startswith("delete_appt_"))
async def confirm_delete_appointment(callback: types.CallbackQuery, state: FSMContext):
    appt_id = int(callback.data.removeprefix("delete_appt_"))
    await state.update_data(appt_id=appt_id)

    # Кнопки для подтверждения удаления
    confirm_button = InlineKeyboardButton(text="✅ Да", callback_data="confirm_delete_yes")
    cancel_button = InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[confirm_button, cancel_button]])

    await callback.message.edit_text("Вы точно хотите удалить это назначение?", reply_markup=keyboard)

# Обработчик подтверждения удаления
@router.callback_query(F.data == "confirm_delete_yes")
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
@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Операция удаления отменена.")
    await state.clear()