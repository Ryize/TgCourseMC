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


def get_training():
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


thread = threading.Thread(target=get_training)
thread.start()


def get_pay():
    while True:
        time.sleep(15)
        for i in pay_data:
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
                requests.post(
                    PAYMENT_API + pay_data[i]["name"] + "/", timeout=5
                )
                pay_data[i] = {}


thread = threading.Thread(target=get_pay)
thread.start()
