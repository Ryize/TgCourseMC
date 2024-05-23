"""
Модуль содержит клавиатуры, используемые.
"""

from telebot import types


class KeyboardMixin:
    """
    Клас содержит основные клавиатуры, используемые в боте.
    """

    @staticmethod
    def main_kb():
        """
        Клавиатура авторизации
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Авторизация🔑")
        kb.row(btn1)
        return kb

    @staticmethod
    def user_kb():
        """
        Клавиатура действий, доступных для пользователя.
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Оплата 💰")
        btn2 = types.KeyboardButton("Пропустить занятие 💤")
        btn3 = types.KeyboardButton("Пинг ⚾")
        kb.row(btn1, btn3)
        kb.row(btn2)
        return kb

    @staticmethod
    def skip_lesson_kb():
        """
        Клавиатура пропуска занятия или занятий.
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton(" 1 💤")
        btn2 = types.KeyboardButton(" 2 💤💤")
        btn3 = types.KeyboardButton(" 3 💤💤💤")
        kb.row(btn1, btn2, btn3)
        return kb

    @staticmethod
    def skip_lesson_kb2():
        """
        Клавиатура подтверждения пропуска занятия.
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Да 👍")
        btn2 = types.KeyboardButton("Нет 👎")
        kb.row(btn1, btn2)
        return kb

    @staticmethod
    def admin_kb():
        """
        Клавиатура администратора.
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Заявки 📝")
        btn2 = types.KeyboardButton("Отправить сообщение всем 📣")
        btn3 = types.KeyboardButton("Пинг ⚾")
        kb.row(btn1, btn3)
        kb.row(btn2)
        return kb
