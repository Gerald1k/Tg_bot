from aiogram import Router, F
from keyboards.main_menu import main_keyboard
from aiogram.types import(
    Message
    )
from sqlalchemy import select, delete

from db import async_session, UserData
router = Router() 

def calculate_kbju(weight, goal):
    """Функция для расчета КБЖУ в зависимости от цели."""
    proteins = weight * 1.5
    fats = weight - 10
    if goal == "Набор мышечной массы":
        carbs = weight * 4
        carbs2 = weight * 3
        calories = proteins * 4 + fats * 9 + carbs * 4
        calories2 = proteins * 4 + fats * 9 + carbs2 * 4
        expected_change = (calories - calories2) * 30 / 7.9
        change_text = f"Прогнозируемый прирост в месяц: {int(expected_change)} г"
    elif goal == "Снижение веса":
        carbs = weight * 1.5
        carbs2 = weight * 3
        calories = proteins * 4 + fats * 9 + carbs * 4
        calories2 = proteins * 4 + fats * 9 + carbs2 * 4
        expected_change = abs(calories - calories2) * 30 / 7.9
        change_text = f"Прогнозируемая потеря в месяц: {int(expected_change)} г"
    else:  # Поддержание формы
        carbs = weight * 3
        calories = proteins * 4 + fats * 9 + carbs * 4
        change_text = "Прогнозируемых изменений в массе нет"
    
    return proteins, fats, carbs, calories, change_text


@router.message(F.text == "🍽 Рекомендации по КБЖУ")
async def kbju_recommendation(message: Message):
    # Достаём из БД вес и цель пользователя
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

    # Расчёт КБЖУ
    proteins, fats, carbs, calories, change_text = calculate_kbju(weight, goal)

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