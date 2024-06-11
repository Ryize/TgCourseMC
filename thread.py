"""
Модуль для работы с функциями, выполняющими периодические задачи в
Telegram-боте.

Этот модуль содержит функции для выполнения периодических задач в
Telegram-боте, таких как проверка новых заявок на тренировки и обработка
платежей. Он использует механизм многопоточности для выполнения задач в фоновом
режиме, не блокируя основной поток выполнения бота.

Пример использования:

    import os
    import threading
    import time
    import requests

    from api_worker import get_application
    from billing import check_payment
    from bot import TG_ID_ADMIN, bot, pay_data
    from models import *

    TOKEN = os.getenv("TOKEN")
    PAYMENT_API = os.getenv("PAYMENT_API")

    # Описание функции get_training()
    # Описание функции get_pay()

    # Создание потоков для выполнения задач
    thread_training = threading.Thread(target=get_training)
    thread_training.start()

    thread_payment = threading.Thread(target=get_pay)
    thread_payment.start()
"""

import os
import time

import requests

from api_worker import get_application, get_review
from billing import check_payment
from bot import TG_ID_ADMIN, bot, pay_data
from models import *

TOKEN = os.getenv("TOKEN")
PAYMENT_API = os.getenv("PAYMENT_API")


def get_training():
    """
    Функция периодически проверяет наличие новых заявок на тренировки и
    отправляет уведомления администратору о новых заявках.

    Функция работает в бесконечном цикле, с периодом 60 секунд. На каждой
    итерации проверяет базу данных на наличие новых заявок на тренировки.
    Если обнаруживается новая заявка, отправляется уведомление администратору
    с деталями заявки, и заявка добавляется в базу данных.
    """
    while True:
        time.sleep(60)
        for i in get_application():
            app = (
                Application.select()
                .where(Application.id_application == i["id"])
                .first()
            )
            if app:
                pass
            else:
                bot.send_message(
                    TG_ID_ADMIN,
                    f"У вас новая заявка!\n"
                    f'Имя: {i["name"]}\n'
                    f'Контакт: {i["contact"]}\n'
                    f'Почта: {i["email"]}\n'
                    f'Дата заявки: {i["created_at"]}',
                )
                app = Application(id_application=i["id"])

                app.save()


def get_pay():
    """
    Функция периодически проверяет состояние платежей и отправляет уведомления
    об успешно проведенных платежах.

    Функция работает в бесконечном цикле, с периодом 15 секунд. На каждой
    итерации проверяет состояние каждого платежа в словаре `pay_data`.
    Если платеж успешно проведен, отправляются уведомления пользователю и
    администратору, а также делается POST-запрос к внешнему API для
    обработки платежа.
    """
    while True:
        time.sleep(15)
        for i in pay_data.items():
            if pay_data.get(i) and check_payment(
                pay_data[i]["payment_id"], pay_data[i]["amount"]
            ):
                bot.send_message(i, "Ваш платеж успешно прошел!")
                bot.send_message(
                    TG_ID_ADMIN,
                    f"Поступил платеж от: "
                    f'{pay_data[i]["name"]}\n'
                    f"ID платежа: "
                    f'{pay_data[i]["payment_id"]}\n'
                    f"на сумму: "
                    f'{pay_data[i]["amount"]}',
                )
                requests.post(PAYMENT_API + pay_data[i]["name"] + "/", timeout=5)
                pay_data[i] = {}


def review():
    while True:
        time.sleep(5)
        for i in get_review()["reviews"]:
            rev = (
                Review.select()
                .where(Review.id_review == i["id"])
                .first()
            )
            if rev:
                pass
            else:
                bot.send_message(
                    TG_ID_ADMIN,
                    f"Пришёл проект на ревью!\n"
                    f'Ссылка: {i["github"]}\n'
                    f'Коментарий: {i["comment"]}\n'
                )
                rev = Review(id_review=i["id"])

                rev.save()
