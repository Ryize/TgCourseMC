"""
Модуль отвечает за работу с api, зарегистрированных пользователей сайта
"""

import json
import os

import requests

STUDENT_API = os.getenv("STUDENT_API")
PAYMENT_API = os.getenv("PAYMENT_API")
APPLICATION_API = os.getenv("APPLICATION_API")
REVIEW_API = os.getenv("REVIEW_API")


def get_data() -> dict:
    """
    Функция получения донных из api.
    """
    data_no_json = requests.get(STUDENT_API, timeout=5).text
    data = json.loads(data_no_json)
    return data


def get_payment(username) -> dict:
    """
    Функция получает данные из API платежей
    """
    data_no_json = requests.get(PAYMENT_API + username + "/", timeout=5).text
    amount = json.loads(data_no_json)
    return amount


def get_application() -> dict:
    """
    Функция получает данные из API заявок
    """
    data_json = requests.get(APPLICATION_API, timeout=5).text
    data = json.loads(data_json)
    return data


def get_review() -> dict:
    """
    Функция получает данные из API ревью
    """
    data_json = requests.get(REVIEW_API, timeout=5).text
    data = json.loads(data_json)
    return data
