"""
Модуль для создания и настройки Telegram-бота с использованием
библиотеки telebot.

Этот модуль предоставляет функциональность для создания и настройки
Telegram-бота с помощью библиотеки telebot. Он включает в себя импорт
необходимых модулей, установку токена доступа к API Telegram, и создание
объекта TeleBot для взаимодействия с Telegram API.

Пример использования:

    import os
    import telebot

    # Получаем токен доступа к API Telegram из переменных окружения
    TOKEN = os.getenv("TOKEN")

    # Создаем объект бота с использованием полученного токена
    bot = telebot. TeleBot(TOKEN)

Этот модуль может быть дополнен различными функциями для обработки команд,
сообщений и событий, которые бот может получать от пользователей Telegram.
Например, обработка команд, отправка сообщений,
обработка клавиатуры и т. д.

Для работы с Telegram API необходимо установить библиотеку telebot:

    pip install pyTelegramBotAPI
"""

import os

import telebot

STUDENT_API = os.getenv('STUDENT_API')
PAYMENT_API = os.getenv('PAYMENT_API')
APPLICATION_API = os.getenv('APPLICATION_API')
REVIEW_API = os.getenv('REVIEW_API')
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)
account_id = os.environ.get('SHOP_ID')
secret_key = os.environ.get('SECRET_KEY')
