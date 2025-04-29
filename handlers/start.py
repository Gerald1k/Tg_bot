from aiogram import Router, types
from aiogram.filters import CommandStart
from keyboards.main_menu import main_keyboard

router = Router() 
# /start
@router.message(CommandStart())
async def start_handler(message: types.message):
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    await message.answer(
        f"👋 Привет, {username}! Я помогу вам вести вашу медицинскую карту.\n\n"
        "Здесь вы можете ввести свои данные, следить за анализами, получать рекомендации по питанию и многое другое. "
        "Чтобы начать, выберите одну из опций в главном меню ниже.",
        reply_markup=main_keyboard
    )