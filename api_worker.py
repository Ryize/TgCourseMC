"""
Модуль отвечает за работу с api зарегестрированых пользователей сайта
"""
import json
import os


import requests

STUDENT_API = os.getenv("STUDENT_API")
PAYMENT_API = os.getenv("PAYMENT_API") + 'MatveyChekashov/'


def get_data():
    """
    Функция получения донных из api.
    """
    data_no_json = requests.get(STUDENT_API, timeout=5).text
    data = json.loads(data_no_json)
    return data

def get_payment():
    """
    Функция получает данные из API платежей
    """
    data_no_json = requests.get(PAYMENT_API, timeout=5).text
    data = json.loads(data_no_json)
    return data
