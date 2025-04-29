from aiogram import Router, types, F
from states.del_states import DeleteAllData
from aiogram.fsm.context import FSMContext
from sqlalchemy import delete

from db import async_session, UserData, Analysis, DoctorAppointment, InstrumentalExamination, Recommendation
from states.del_states import DeleteAllData 

router = Router() 

@router.message(F.text == "❌ Удалить все данные")
async def start_delete_all_data(message: types.Message, state: FSMContext):
    await message.answer(
        "🚨 <b>ВСЕ ВАШИ ДАННЫЕ будут УДАЛЕНЫ!</b>\n\n"
        "Чтобы подтвердить, введите: <b>ПОДТВЕРЖДАЮ</b>\n\n"
        "Если передумали - напишите что-угодно другое.",
        parse_mode="HTML"
    )
    await state.set_state(DeleteAllData.waiting_for_confirmation)

# Обработка ответа
@router.message(DeleteAllData.waiting_for_confirmation)
async def process_delete_confirmation(message: types.Message, state: FSMContext):
    if message.text.strip().upper() == "ПОДТВЕРЖДАЮ":
        telegram_id = message.from_user.id
        async with async_session() as session:
            # Удаляем данные из всех таблиц
            await session.execute(delete(Analysis).where(Analysis.telegram_id == telegram_id))
            await session.execute(delete(DoctorAppointment).where(DoctorAppointment.telegram_id == telegram_id))
            await session.execute(delete(InstrumentalExamination).where(InstrumentalExamination.telegram_id == telegram_id))
            await session.execute(delete(Recommendation).where(Recommendation.telegram_id == telegram_id))
            await session.execute(delete(UserData).where(UserData.telegram_id == telegram_id))
            await session.commit()

        await message.answer("🔍 Все ваши данные были успешно удалены."
        )
    else:
        await message.answer("🚫 Удаление отменено.")

    await state.clear()