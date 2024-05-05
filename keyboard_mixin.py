"""
Модуль содержит клавиатуры, используемые
"""

from telebot import types


class KeyboardMixin:
    def main_kb(self):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Авторизация🔑")
        kb.row(btn1)
        return kb
