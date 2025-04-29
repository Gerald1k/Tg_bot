from aiogram import Router, F
from keyboards.main_menu import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import(
    Message,
    CallbackQuery
    )
from sqlalchemy import select

from db import async_session, Recommendation
router = Router() 

@router.message(F.text == "📊 Рекомендации")
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
@router.callback_query(F.data.startswith("rec_cat|"))
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
@router.callback_query(F.data == "rec_back")
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