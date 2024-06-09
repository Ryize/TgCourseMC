"""
Модуль с логикой работы действий админа.
"""

from config import bot
from keyboard_mixin import KeyboardMixin
from models import User

TG_ID_ADMIN = 814401631

kb = KeyboardMixin()


def admin_actions(message, user):
    """
    В этой функции бот здоровается с админом и кидает ему
    админовскую клавиатуру.
    """

    bot.send_message(
        message.chat.id, f"Здравствуй, " f"{user.name}!", reply_markup=kb.admin_kb()
    )


@bot.message_handler(func=lambda message: message.text == "Отправить сообщение всем 📣")
def message_admin(message):
    bot.send_message(TG_ID_ADMIN, "Введите текст: ")
    bot.register_next_step_handler(message, send_message_to_all_users)


def send_message_to_all_users(message):
    user = User.select()
    for i in user:
        if i.chat_id == TG_ID_ADMIN:
            pass
        else:
            bot.send_message(i.chat_id, f'Админинстратор: {message.text}')


