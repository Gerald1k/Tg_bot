from aiogram.fsm.state import StatesGroup, State

# Состояния FSM
class DeleteAllData(StatesGroup):
    waiting_for_confirmation = State()