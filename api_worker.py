"""
Модуль отвечает за работу с api, зарегистрированных пользователей сайта
"""

import json
import os

import requests

from config import PAYMENT_API, APPLICATION_API, REVIEW_API


COURSEMC_API_BASE_URL = os.getenv(
    'COURSEMC_API_BASE_URL',
    'https://coursemc.ru/api/v1',
).rstrip('/')
COURSEMC_BOT_API_TOKEN = os.getenv('COURSEMC_BOT_API_TOKEN', '')


def _bot_headers() -> dict:
    """Не позволяет случайно обратиться к закрытому API без секрета."""
    if not COURSEMC_BOT_API_TOKEN:
        raise RuntimeError('Не задан COURSEMC_BOT_API_TOKEN')
    return {'X-CourseMC-Bot-Token': COURSEMC_BOT_API_TOKEN}


def authenticate_student(login: str, password: str) -> dict:
    """Проверяет ученика на сайте, не загружая логины и пароли остальных."""
    response = requests.post(
        f'{COURSEMC_API_BASE_URL}/bot/authenticate/',
        json={'login': login, 'password': password},
        headers=_bot_headers(),
        timeout=5,
    )
    if response.status_code == 401:
        return {'authenticated': False}
    response.raise_for_status()
    return response.json()


def get_group_student_usernames(group_id: int) -> list:
    """Возвращает канонические логины действующих учеников группы."""
    response = requests.get(
        f'{COURSEMC_API_BASE_URL}/bot/groups/{group_id}/students/',
        headers=_bot_headers(),
        timeout=5,
    )
    response.raise_for_status()
    return response.json().get('usernames', [])


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


def get_questions(category: str, amount: int, difficulty: int = None) -> dict:
    """
    Получает данные о вопросах из API.

    Args:
        category (str): тема вопросов.
        amount (int): количество вопросов.
        difficulty (int, optional): Уровень сложности. Если не указан, не включается в запрос.

    Returns:
        dict: Вопросы в виде словаря.
    """
    if difficulty is None:
        data = json.loads(requests.get(
            f'https://coursemc.ru/api/v1/interview_question/?category={category}&amount={amount}').text)
        return data
    data = json.loads(requests.get(
        f'https://coursemc.ru/api/v1/interview_question/'
        f'?category={category}&amount={amount}&level={difficulty}').text)
    return data


def get_weekday_timetable(weekday: str):
    """
    Получает расписание занятий на конкретный день недели.

    Args:
        weekday (str): День недели. Пишется на русском языке с большой буквы.
        Пример: Понедельник, Вторник и т.д.
    """
    data = json.loads(
        requests.get(
            f'https://coursemc.ru/api/v1/classes_timetable_weekday/{weekday}/').text
    )
    return data


def get_interview_question(category, amount=1, level=None) -> str:
    """
    Получает вопрос для сервиса с GPT.

    Returns:
        str: вопрос
    """
    url = (f'https://coursemc.ru/api/v1/interview_question/?'
           f'category={category}&amount={amount}')
    if level:
        url += f'&level={level}'
    data = json.loads(
        requests.get(url).text
    )
    return data


def check_interview_question(question: str, answer: str) -> str:
    """
    Отправляет вопрос и ответ пользователя для проверки.

    Args:
        question (str): вопрос
        answer (str): ответ пользователя

    Returns:
        str: результат оценки
    """
    entered_data = {
        'question': question,
        'answer': answer,
    }
    data = requests.get(
        f'https://coursemc.ru/api/v1/ai_check_question/',
        params=entered_data).text
    data = json.loads(data)
    return data['score']
