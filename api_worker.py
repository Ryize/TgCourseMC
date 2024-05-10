"""
Модуль отвечает за работу с api зарегестрированых пользователей сайта
"""
import json
import os


import requests

STUDENT_API = os.getenv("STUDENT_API")


def get_data():
    """
    Функция получения донных из api
    """
    data_no_json = requests.get(STUDENT_API).text
    data = json.loads(data_no_json)
    return data
