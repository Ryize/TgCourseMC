"""
Модуль с логикой работы бота
"""

import os

import telebot

from api_worker import get_data
from keyboard_mixin import KeyboardMixin
from models import *

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)
kb = KeyboardMixin()

temp_data = {}


@bot.message_handler(commands=["start"])
def welcome(message):
    """
    Функция приветствия, принимает команду "start",
    выдает приветственное сообщение и клавиатуру авторизации,
    создает вложенный словарь в словаре temp_data, для хранения данных,
    введенных пользователем
    """
    bot.send_message(
        message.chat.id,
        "Добро пожаловать в бота CourceMC!\n"
        " Для продолжения работы, авторизуйтесь,"
        " используя логин и пароль, указанный "
        "при регистрации на сайте курса!",
        reply_markup=kb.main_kb(),
    )
    bot.register_next_step_handler(message, login)


@bot.message_handler(func=lambda message: message.text == "Авторизация🔑")
def login(message):
    """
    Функция принимает сообщение с main_kb, запрашивает сообщением
    логин пользователя, ожидает ввода данных пользователем
    """
    temp_data[message.chat.id] = {}
    bot.send_message(
        message.chat.id, "Введите логин, указанный при регистрации на сайте."
    )
    bot.register_next_step_handler(message, password)


def password(message):
    """
    Функция принимает логин пользователя в виде сообщения,
    сохраняет его в словаре и запрашивает пароль.
    Ожидает ввода пароля
    """
    bot.send_message(message.chat.id, "Введите пароль")
    bot.register_next_step_handler(message, check_autorization)
    temp_data[message.chat.id]["login"] = message.text


def check_autorization(message):
    """
    Функция принимает пароль в виде сообщения, сохраняет его в словарь,
    после этого осуществляет проверку логина и пароля с данными из api,
    при совпадении выдает клавиатуру действий пользователя,
    при не совпадении - сообщение с ошибкой.
    """
    temp_data[message.chat.id]["password"] = message.text
    flag = False
    for i in get_data():
        if (
                i["name"] == temp_data[message.chat.id]["login"]
                and i["password"] == temp_data[message.chat.id]["password"]
        ):
            flag = True
    if flag:
        bot.send_message(
            message.chat.id,
            f'Привет, {temp_data[message.chat.id]["login"]}!',
            reply_markup=kb.user_kb()
        )
    else:
        bot.send_message(
            message.chat.id, "Неправильно введены данные!",
        )
        login(message)

@bot.message_handler(func=lambda message: message.text == "Пинг ⚾")
def button_ping(message):
    """
    Действия бота при нажатии кнопки "Пинг ⚾"

    Эта кнопка нужна для того, чтобы проверить, что бот работает.
    Если он работает, он пишет пользователю "Понг" на его нажатие кнопки "Пинг".
    """
    bot.send_message(
        message.chat.id, "Понг ⚾"
    )
