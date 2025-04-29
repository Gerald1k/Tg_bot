from aiogram.fsm.state import StatesGroup, State

class AppointmentFlow(StatesGroup):
    date = State()
    doctor = State()
    recommendation = State()
    next_action = State()

class EditAppointmentState(StatesGroup):
    waiting_for_text = State()
