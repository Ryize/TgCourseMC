"""
Модуль содержит клавиатуры, используемые в телеграм-боте.
"""

from telebot import types


class KeyboardMixin:
    """
    Класс содержит основные клавиатуры, используемые в боте.
    """

    @staticmethod
    def main_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру авторизации.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопкой "Авторизация🔑".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Авторизация🔑')
        kb.row(btn1)
        return kb

    @staticmethod
    def user_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру авторизации.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопкой "Авторизация🔑".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Оплата 💰')
        btn2 = types.KeyboardButton('Пропустить занятие 💤')
        btn3 = types.KeyboardButton('Пинг ⚾')
        kb.row(btn1, btn3)
        kb.row(btn2)
        return kb

    @staticmethod
    def skip_lesson_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру пропуска занятия или занятий.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопками "1 💤",
            "2 💤💤" и "3 💤💤💤".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton(' 1 💤')
        btn2 = types.KeyboardButton(' 2 💤💤')
        btn3 = types.KeyboardButton(' 3 💤💤💤')
        kb.row(btn1, btn2, btn3)
        return kb

    @staticmethod
    def skip_lesson_kb2() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру подтверждения пропуска занятия.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопками "Да 👍"
            и "Нет 👎".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Да 👍')
        btn2 = types.KeyboardButton('Нет 👎')
        kb.row(btn1, btn2)
        return kb

    @staticmethod
    def admin_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру администратора.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопками "Заявки 📝",
            "Отправить сообщение всем 📣" и "Пинг ⚾".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Заявки 📝')
        btn2 = types.KeyboardButton('Отправить сообщение всем 📣')
        btn3 = types.KeyboardButton('Пинг ⚾')
        kb.row(btn1, btn3)
        kb.row(btn2)
        return kb
