"""
Модуль с логикой работы бота
"""

import os

import telebot

from keyboard_mixin import KeyboardMixin

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)
kb = KeyboardMixin()


@bot.message_handler(commands=["start"])
def welcome(message):
    bot.send_message(
        message.chat.id,
        "Добро пожаловать в бота CourceMC!\n"
        "Для продолжения работы, авторизуйтесь,"
        "используя логин и пароль, указанный "
        "при регистрации на сайте курса!",
        reply_markup=kb.main_kb(),
    )


@bot.message_handler(func=lambda message: message.text == "Авторизация🔑")
def login(message):
    bot.send_message(
        message.chat.id,
        "Введите логин, указанный при регистрации на сайте."
    )
    bot.register_next_step_handler(message, password)


def password(message):
    bot.send_message(
        message.chat.id,
        "Введите пароль"
    )


def check_autorization():
    pass
