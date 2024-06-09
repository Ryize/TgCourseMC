"""
Модуль с логикой работы бота
"""

import datetime
import os
import telebot

import requests

from admin import admin_actions
from api_worker import get_data, get_payment
from billing import get_payment_url
from config import bot
from keyboard_mixin import KeyboardMixin
from models import User

TG_ID_ADMIN = 814401631

kb = KeyboardMixin()

temp_data = {}
pay_data = {}
number_of_passes = {}


@bot.message_handler(commands=["start"])
def welcome(message):
    """
    Функция приветствия, принимает команду "start",
    выдает приветственное сообщение и сравнивает tg id пользователя с tg id
    в таблице users.db. Если tg id пользователя есть в базе, то пользователю
    выдаётся клавиатура users_kb, иначе выдаёт кнопку "Авторизация".
    Если зашёл админ, то она сравнивает его tg id c id админа в базе и
    если id совпало, бот выдаёт приветствие админу и его индивидуальную
    клавиатуру.
    """
    try:
        user = User.select().where(User.chat_id == message.chat.id).first()
        bot.send_message(
            message.chat.id,
            f"Здравствуй, {user.name}"
        )
    except AttributeError:
        bot.send_message(
            message.chat.id,
            "Добро пожаловать в бота CourceMC!\n"
            " Для продолжения работы, авторизуйтесь,"
            " используя логин и пароль, указанный "
            "при регистрации на сайте курса!",
            reply_markup=kb.main_kb(),
        )


@bot.message_handler(func=lambda message: message.text == "Авторизация🔑")
def login(message):
    """
    Функция принимает сообщение с main_kb, запрашивает сообщением
    логин пользователя, ожидает ввода данных пользователем
    """
    temp_data[message.chat.id] = {}
    keyboard = telebot.types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id, "Введите логин, указанный при регистрации на сайте.",
    reply_markup=keyboard)
    bot.register_next_step_handler(message, password)


def password(message):
    """
    Функция принимает логин пользователя в виде сообщения,
    сохраняет его в словаре и запрашивает пароль.
    Ожидает ввода пароля.
    """
    bot.send_message(message.chat.id, "Введите пароль:")
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
        user = User(
            chat_id=message.chat.id, name=temp_data[message.chat.id]["login"]
        )

        user.save()
        if message.chat.id == TG_ID_ADMIN:
            admin_actions(message, user)
        else:
            bot.send_message(
                message.chat.id,
                f'Привет, {temp_data[message.chat.id]["login"]}!',
                reply_markup=kb.user_kb(),
            )
            temp_data[message.chat.id] = {}
    else:
        bot.send_message(
            message.chat.id,
            "Неправильно введены данные!",
        )
        login(message)


@bot.message_handler(func=lambda message: message.text == "Пинг ⚾")
def button_ping(message):
    """
    Действия бота при нажатии кнопки "Пинг ⚾"

    Эта кнопка нужна для того, чтобы проверить, что бот работает.
    Если он работает, он пишет пользователю "Понг" на его нажатие
    кнопки "Пинг".
    """
    bot.send_message(message.chat.id, "Понг ⚾")


@bot.message_handler(
    func=lambda message: message.text == "Пропустить занятие 💤"
)
def skip_lesson_buttons(message):
    """
    Функция принимает с клавиатуры user_kb сообщение о пропуске занятия(й) и
    выдаёт клавиатуру выбора количества занятий, которые пользователь желает
    пропустить.
    """
    bot.send_message(
        message.chat.id,
        "Сколько занятий хотите пропустить?",
        reply_markup=kb.skip_lesson_kb(),
    )

    @bot.message_handler(
        func=lambda message: message.text in ["1 💤", "2 💤💤", "3 💤💤💤"]
    )
    def confirmation_skip_lesson(message):
        """
        Принимает данные с клавиатуры skip_lesson_kb, занося данные
        о пропуске занятия(й) в словарь number_of_passes с ключом
        "lessons". Также запрашивает подтверждение пользователя о
        пропуске занятия(й).
        """
        bot.send_message(
            message.chat.id,
            "Точно хотите пропустить занятие(я)?",
            reply_markup=kb.skip_lesson_kb2(),
        )
        if message.text == "1 💤":
            number_of_passes["lessons"] = 1
        elif message.text == "2 💤💤":
            number_of_passes["lessons"] = 2
        elif message.text == "3 💤💤💤":
            number_of_passes["lessons"] = 3
        @bot.message_handler(func=lambda message: message.text == "Да 👍")
        def pass_lesson(message):
            """
            Действия бота при подтверждении пропуска занятий пользователем
            по кнопке "Да 👍".

            На сайт отправляется post запрос(ы) (в зависимости от
            количества пропусков) с именем пользователя и датой пропуска
            занятия(й). Также админу присылается уведомление о пропуске
            занятия(й) определённым пользователем, а пользователю бот
            сообщает об успешной записи количества пропусков занятий и
            высылает ему клавиатуру user_kb.
            """
            api_missing = os.getenv("API_MISSING")
            user = User.select().where(User.chat_id == message.chat.id).first()
            date = datetime.date.today() + datetime.timedelta(days=1)
            for i in range(number_of_passes["lessons"]):#Для чего цикл если i не используется?
                requests.post(
                    api_missing,
                    data={
                        "username": user.name,
                        "date": date.strftime("%Y-%m-%d")
                    }, timeout=5
                )
                date += datetime.timedelta(days=2)
            bot.send_message(
                TG_ID_ADMIN,
                f"❗️ Ученик {user.name} пропускает"
                f" {number_of_passes['lessons']} занятие(я) ❗️",
            )
            bot.send_message(
                message.chat.id,
                "Ваше количество пропусков занятий успешно записано!",
                reply_markup=kb.user_kb(),
            )

        @bot.message_handler(func=lambda message: message.text == "Нет 👎")
        def no_pass_lesson(message):
            """
            Если пользователь передумал и отказался пропускать занятие(я),
            нажав на кнопку "Нет 👎", ему бот отсылает сообщение и высылает
            клавиатуру user_kb.
            """
            bot.send_message(
                message.chat.id,
                "Хорошо, что вы отказались пропускать занятие(я) 👍👍👍",
                reply_markup=kb.user_kb(),
            )


@bot.message_handler(func=lambda message: message.text == "Оплата 💰")
def pay(message):
    user = User.select().where(User.chat_id == message.chat.id).first()
    amount = get_payment(user.name)["amount"]
    if amount <= 0:
        bot.send_message(message.chat.id, 'Вы уже оплатили занятия!')
        return
    payment = get_payment_url(amount)
    bot.send_message(
        message.chat.id, f"Оплатите {amount} рублей, по ссылке: {payment[0]}"
    )
    pay_data[message.chat.id] = {
        "amount": amount,
        "payment_id": payment[1],
        "name": user.name,
    }
