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

    def user_kb(self):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Оплата 💰")
        btn2 = types.KeyboardButton("Пропустить занятие 💤")
        btn3 = types.KeyboardButton("Пинг ⚾")
        kb.row(btn1, btn3)
        kb.row(btn2)
        return kb

    def skip_lesson_kb(self):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Да')
        btn2 = types.KeyboardButton('Нет')
        kb.row(btn1, btn2)
        return kb