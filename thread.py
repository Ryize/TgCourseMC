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

    TOKEN = os.getenv('TOKEN')
    PAYMENT_API = os.getenv('PAYMENT_API')

    # Описание функции get_training()
    # Описание функции get_pay()

    # Создание потоков для выполнения задач
    thread_training = threading.Thread(target=get_training)
    thread_training.start()

    thread_payment = threading.Thread(target=get_pay)
    thread_payment.start()
"""
import json
import os
import time

import requests

from admin import send_admin_timetable, get_weekday
from api_worker import (get_application, get_group_student_usernames,
                        get_review, get_weekday_timetable)
from billing import check_payment
from bot import TG_ID_ADMIN, bot, pay_data
from config import YANDEX_TOKEN
from models import *

TOKEN = os.getenv('TOKEN')
PAYMENT_API = os.getenv('PAYMENT_API')


def get_training() -> None:
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
                .where(Application.id_application == i['id'])
                .first()
            )
            if not app:
                bot.send_message(
                    TG_ID_ADMIN,
                    f'У вас новая заявка!\n'
                    f'Имя: {i["name"]}\n'
                    f'Контакт: {i["contact"]}\n'
                    f'Почта: {i["email"]}\n'
                    f'Дата заявки: {i["created_at"]}',
                )
                app = Application(id_application=i['id'])

                app.save()


def get_pay() -> None:
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
        for i in pay_data.keys():
            if pay_data.get(i) and check_payment(
                    pay_data[i]['payment_id'], pay_data[i]['amount']
            ):
                bot.send_message(i, 'Ваш платеж успешно прошел!')
                bot.send_message(
                    TG_ID_ADMIN,
                    f'Поступил платеж от: '
                    f'{pay_data[i]["name"]}\n'
                    f'ID платежа: '
                    f'{pay_data[i]["payment_id"]}\n'
                    f'на сумму: '
                    f'{pay_data[i]["amount"]}',
                )
                requests.post(PAYMENT_API + pay_data[i]['name'] + '/',
                              timeout=5)
                pay_data[i] = {}


def review() -> None:
    """
    Функция периодически проверяет наличие новых отзывов и отправляет
    уведомления администратору о новых отзывах.

    Функция работает в бесконечном цикле с периодом 60 секунд. На каждой
    итерации проверяет наличие новых отзывов с помощью функции get_review().
    Если обнаруживается новый отзыв, отправляется уведомление администратору
    с деталями отзыва, и отзыв сохраняется в базу данных.
    """
    while True:
        time.sleep(60)
        for i in get_review()['reviews']:
            rev = Review.select().where(Review.id_review == i['id']).first()
            if not rev:
                bot.send_message(
                    TG_ID_ADMIN,
                    f'Пришёл проект на ревью!\n'
                    f'Ссылка: {i["github"]}\n'
                    f'Коментарий: {i["comment"]}\n',
                )
                rev = Review(id_review=i['id'])

                rev.save()


def send_timetable_to_administrator() -> None:
    """
    Функция каждую полночь отправляет Администратору сообщение о всех уроков
    за текущий день.

    Функция работает в бесконечном цикле.
    """
    while True:
        now = datetime.datetime.now()
        midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0,
                                                              second=0,
                                                              microsecond=0)
        seconds_until_midnight = (midnight - now).total_seconds()

        # Ждем до следующей полуночи
        time.sleep(seconds_until_midnight)
        send_admin_timetable()


def check_time(target_time_str: str) -> bool:
    """
    Проверить время до начала урока в минутах.

    Args:
        target_time_str: str (время в формате 12:20)

    Returns:
        bool: True - если до урока от 1 до 5 минут, иначе False
    """
    # Получаем текущее время
    now = datetime.datetime.now()

    # Преобразуем строку времени в объект datetime
    target_time = datetime.datetime.strptime(target_time_str, "%H:%M")

    # Заменяем дату целевого времени на сегодняшнюю
    target_time = target_time.replace(year=now.year, month=now.month, day=now.day)

    # Вычисляем разницу во времени в минутах
    diff = (target_time - now).total_seconds() / 60

    # Проверяем, остаётся ли от 1 до 5 минут до целевого времени
    if 1 <= diff <= 5:
        return True
    return False


def get_lesson_link() -> str:
    """
    Возвращает ссылку на урок в Яндекс Телемост

    Returns:
        str: ссылка
    """
    headers = {
        'Authorization': YANDEX_TOKEN,
        'Content-Type': 'application/json',
    }

    data = json.loads(requests.post(
        'https://cloud-api.yandex.net/v1/telemost-api/conferences',
        headers=headers).text)
    return data['join_url']


def send_lesson_link_to_group() -> None:
    """
    Функция отправляет ссылку на урок в телемосте за 5 минут до начала занятия.

    Отправляет всем в учебной группе и администратору.
    """
    while True:
        weekday = get_weekday()
        data = get_weekday_timetable(weekday)

        group_id = None
        for i in data['timetables']:
            if check_time(i['time_lesson'][:5]):
                for group in json.loads(
                        requests.get('https://coursemc.ru/api/v1/groups/').text
                ):
                    if group['title'] == i['group']:
                        group_id = group['id']
        if not group_id:
            time.sleep(60)
            continue

        lesson_url = get_lesson_link()

        bot.send_message(TG_ID_ADMIN, f'👉 Ссылка на урок: {lesson_url}')

        try:
            usernames = get_group_student_usernames(group_id)
        except (requests.RequestException, RuntimeError, ValueError):
            time.sleep(60)
            continue

        for username in usernames:
            user = User.select().where(User.name == username).first()
            if user:
                bot.send_message(
                    int(user.chat_id),
                    f'👉 Ссылка на урок: {lesson_url}',
                )
        time.sleep(900)
