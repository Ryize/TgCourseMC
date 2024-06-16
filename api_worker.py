"""
Модуль отвечает за работу с api, зарегистрированных пользователей сайта
"""

import json

import requests

from config import STUDENT_API, PAYMENT_API, APPLICATION_API, REVIEW_API


def get_student() -> dict:
    """
    Получает данные о студентах из API.

    Returns:
        dict: Данные студентов в виде словаря.
    """
    data_no_json = requests.get(STUDENT_API, timeout=5).text
    data = json.loads(data_no_json)
    return data


def get_payment(username) -> dict:
    """
    Получает данные о платежах пользователя из API.

    Args:
        username (str): Имя пользователя.

    Returns:
        dict: Данные о платежах пользователя в виде словаря.
    """
    data_no_json = requests.get(
        f'{PAYMENT_API}{username}/', timeout=5).text
    amount = json.loads(data_no_json)
    return amount


def get_application() -> dict:
    """
    Получает данные о заявках из API.

    Returns:
        dict: Данные о заявках в виде словаря.
    """
    data_json = requests.get(APPLICATION_API, timeout=5).text
    data = json.loads(data_json)
    return data


def get_review() -> dict:
    """
    Получает данные о ревью из API.

    Returns:
        dict: Данные о ревью в виде словаря.
    """
    data_json = requests.get(REVIEW_API, timeout=5).text
    data = json.loads(data_json)
    return data
