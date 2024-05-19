"""
Модуль с логикой работы действий админа.
"""

from config import bot
from keyboard_mixin import KeyboardMixin

kb = KeyboardMixin()


def admin_actions(message, user):
    """
    В этой функции бот здоровается с админом и кидает ему админовскую клавиатуру.
    """

    bot.send_message(
        message.chat.id, f"Здравствуй, {user.name}!", reply_markup=kb.admin_kb()
    )
