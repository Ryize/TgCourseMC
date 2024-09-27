"""
Модуль с логикой работы действий админа.
"""
import datetime

from api_worker import get_application, get_weekday_timetable
from config import bot
from keyboard_mixin import KeyboardMixin
from models import User

TG_ID_ADMIN = 814401631

kb = KeyboardMixin()


def admin_actions(message, user):
    """
    В этой функции бот здоровается с админом и кидает ему
    админовскую клавиатуру.
    """

    bot.send_message(
        message.chat.id,
        f'Здравствуй, {user.name}!', reply_markup=kb.admin_kb()
    )


@bot.message_handler(
    func=lambda message: message.text == 'Отправить сообщение всем 📣')
def message_admin(message):
    """
    Обработчик сообщений для администратора.

    Когда администратор отправляет сообщение с текстом "Отправить сообщение
    всем 📣",
    бот запрашивает у администратора текст сообщения, которое будет отправлено
    всем пользователям.

    Args:
        message (telebot.types.Message):
        Сообщение, отправленное администратором.
    """
    bot.send_message(TG_ID_ADMIN, 'Введите текст: ')
    bot.register_next_step_handler(message, send_message_to_all_users)


@bot.message_handler(
    func=lambda message: message.text == 'Заявки 📝')
def application_admin(message):
    """
    Обработчик сообщений для администратора.

    Когда администратор отправляет сообщение с текстом "Заявки 📝",
    бот получает все активные заявки с платформы и отправляет в чат
    администратору.

    Args:
        message (telebot.types.Message):
        Сообщение, отправленное администратором.
    """
    applications = get_application()
    for app in applications:
        bot.send_message(
            TG_ID_ADMIN,
            f'У вас новая заявка!\n'
            f'Имя: {app["name"]}\n'
            f'Контакт: {app["contact"]}\n'
            f'Почта: {app["email"]}\n'
            f'Дата заявки: {app["created_at"]}',
        )


def send_message_to_all_users(message):
    """
    Отправляет сообщение всем пользователям.

    После получения текста сообщения от администратора, функция отправляет
    это сообщение всем пользователям, за исключением администратора.

    Args:
        message (telebot.types.Message): Сообщение с текстом, который нужно
        отправить всем пользователям.
    """
    user = User.select().where(User.chat_id != TG_ID_ADMIN)
    for i in user:
        bot.send_message(i.chat_id, f'Администратор: {message.text}')
    bot.send_message(TG_ID_ADMIN, 'Успешно отправлено!')


@bot.message_handler(
    func=lambda message: message.text == 'Расписание 📆')
def timetable_choice_weekday(message):
    """
    Действия бота при нажатии кнопки 'Расписание 📆'.
    Возвращает кнопки с днями недели.
    """
    chat_id = message.chat.id
    bot.send_message(chat_id,
                     'Выберите день недели:',
                     reply_markup=kb.weekday_buttons())
    bot.register_next_step_handler(message, timetable_view)


def get_weekday() -> str:
    """
    Возвращает текущий день недели (пример: Понедельник, Вторник)

    Returns:
        str: день недели.
    """
    today = datetime.datetime.now()
    days_of_week = ['Понедельник', 'Вторник', 'Среда', 'Четверг',
                    'Пятница',
                    'Суббота', 'Воскресенье']

    # Получаем индекс дня недели (0 = Понедельник, 6 = Воскресенье)
    day_of_week = today.weekday()
    weekday = days_of_week[day_of_week]
    return weekday


def send_admin_timetable(weekday: str = None) -> None:
    """
    Отправка администратору расписания на укаанный день.

    Если день не указан, то берётся текущий.

    Args:
        weekday (str): День недели.
    """
    if not weekday:
        weekday = get_weekday()
    data = get_weekday_timetable(weekday)

    if weekday[-1] == 'а':
        weekday = weekday[:-1] + 'у'

    timetables = []

    for k, i in enumerate(data['timetables']):
        timetables.append([i["group"], i["time_lesson"][:5]])

    timetables = list(sorted(timetables, key=lambda x: int(x[1][:2])))

    msg = f'Расписание на {weekday.lower()}:\n'
    for k, timetable in enumerate(timetables):
        msg += f'{k + 1}) {timetable[0]}: {timetable[1]}\n'
    bot.send_message(TG_ID_ADMIN, msg, reply_markup=kb.admin_kb())


def timetable_view(message):
    """
    Просмотр расписания на указанный день недели.
    """
    send_admin_timetable(message.text)
