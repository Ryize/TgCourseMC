"""
Модуль с логикой работы бота
"""

import os

import telebot

from API_Worker import get_data
from keyboard_mixin import KeyboardMixin

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)
kb = KeyboardMixin()

temp_data = {}


@bot.message_handler(commands=["start"])
def welcome(message):
    bot.send_message(
        message.chat.id,
        "Добро пожаловать в бота CourceMC!\n"
        " Для продолжения работы, авторизуйтесь,"
        " используя логин и пароль, указанный "
        "при регистрации на сайте курса!",
        reply_markup=kb.main_kb(),
    )
    bot.register_next_step_handler(message, login)
    temp_data[message.chat.id] = {}


@bot.message_handler(func=lambda message: message.text == "Авторизация🔑")
def login(message):
    bot.send_message(
        message.chat.id, "Введите логин, указанный при регистрации на сайте."
    )
    bot.register_next_step_handler(message, password)


def password(message):
    bot.send_message(message.chat.id, "Введите пароль")
    bot.register_next_step_handler(message, check_autorization)
    temp_data[message.chat.id]["login"] = message.text


def check_autorization(message):
    temp_data[message.chat.id]["password"] = message.text
    flag = False
    for i in get_data():
        print(
            i["name"],
            i["password"],
            temp_data[message.chat.id]["password"],
            temp_data[message.chat.id]["login"],
        )
        if (
                i["name"] == temp_data[message.chat.id]["login"]
                and i["password"] == temp_data[message.chat.id]["password"]
        ):
            flag = True
    if flag:
        bot.send_message(
            message.chat.id, f'Привет, {temp_data[message.chat.id]["login"]}'
        )
    else:
        bot.send_message(
            message.chat.id, "Неправильно введены данные.", reply_markup=kb.main_kb()
        )


"""
Действия бота при нажатии кнопки "Пинг ⚾"

Эта кнопка нужна для того, чтобы проверить, что бот работает.
Если он работает, он пишет пользователю "Понг" на его нажатие кнопки "Пинг".
"""


@bot.message_handler(func=lambda message: message.text == "Пинг ⚾")
def button_ping(message):
    bot.send_message(
        message.chat.id, "Понг ⚾"
    )
