"""
Модуль с логикой работы действий админа.
"""
from api_worker import get_application
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
