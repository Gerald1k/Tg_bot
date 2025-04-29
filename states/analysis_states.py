from aiogram.fsm.state import StatesGroup, State

class AddAnalysis(StatesGroup):
    date = State()
    select_group = State()
    select_analysis = State()
    select_variant = State()
    result = State()

class DeleteFlow(StatesGroup):
    waiting_for_group = State()
    waiting_for_name = State()
    waiting_for_analysis = State()
    confirm_delete = State()
