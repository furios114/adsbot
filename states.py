from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    category = State()
    description = State()
    contacts = State()


class AdForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_button = State()
    ready_for_publish = State()


class PromoForm(StatesGroup):
    waiting_for_code = State()


class AdminForm(StatesGroup):
    waiting_for_user = State()
    waiting_for_user_remove = State()
    waiting_for_promo_action = State()
    waiting_for_broadcast = State()