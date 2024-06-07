"""
Модуль с логикой работы действий админа.
"""

from config import bot
from keyboard_mixin import KeyboardMixin

kb = KeyboardMixin()


def admin_actions(message, user):
    """
    В этой функции бот здоровается с админом и кидает ему
    клавиатуру администратора.
    """

    bot.send_message(
        message.chat.id, f"Здравствуй, " f"{user.name}!",
        reply_markup=kb.admin_kb()
    )
