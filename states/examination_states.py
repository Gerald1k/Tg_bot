from aiogram.fsm.state import StatesGroup, State

# Определяем состояния FSM
class EditExamStates(StatesGroup):
    desc = State()   # ввод нового описания
    file = State()   # ввод нового файла