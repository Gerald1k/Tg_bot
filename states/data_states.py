from aiogram.fsm.state import StatesGroup, State

class DataStates(StatesGroup):
    fio = State()
    goal = State()
    sport = State()
    height = State()    # Новый шаг: рост
    weight = State()    # Новый шаг: вес
    smoking = State()
    alcohol = State()
    chronic = State()
    heredity = State()
    clinical = State()
    
# FSM-состояния для редактирования данных
class EditStates(StatesGroup):
    field = State()
    value = State()
    
# Добавим FSM‑стейт для удаления
class DeleteStates(StatesGroup):
    confirm = State()
