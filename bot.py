"""
Модуль с логикой работы бота
"""

import datetime
import os

import requests
import telebot

from admin import admin_actions
from api_worker import authenticate_student, get_payment, get_questions, \
    get_interview_question, check_interview_question
from billing import get_payment_url
from config import bot
from keyboard_mixin import KeyboardMixin
from lesson_solutions import register_lesson_solution_handlers
from models import User, Interview, current_date

TG_ID_ADMIN = 814401631

kb = KeyboardMixin()

temp_data = {}
interview_data = {}
pay_data = {}
number_of_passes = {}
interview_question = {}

# Register the persistent review-comment handler before the catch-all handler
# below, so a teacher's next message is consumed by the review workflow.
lesson_solution_handlers = register_lesson_solution_handlers(bot)


@bot.message_handler(commands=['start'])
def welcome(message):
    """
    Функция приветствия, принимает команду 'start',
    выдает приветственное сообщение и сравнивает tg id пользователя с tg id
    в таблице users.db. Если tg id пользователя есть в базе, то пользователю
    выдаётся клавиатура users_kb, иначе выдаёт кнопку 'Авторизация'.
    Если зашёл админ, то она сравнивает его tg id c id админа в базе и
    если id совпало, бот выдаёт приветствие админу и его индивидуальную
    клавиатуру.
    """
    try:
        user = User.select().where(User.chat_id == message.chat.id).first()
        keyboard = kb.user_kb()
        if message.chat.id == TG_ID_ADMIN:
            keyboard = kb.admin_kb()
        bot.send_message(message.chat.id, f'Здравствуй, {user.name}',
                         reply_markup=keyboard)
    except AttributeError:
        bot.send_message(
            message.chat.id,
            'Добро пожаловать в бота CourceMC!\n'
            ' Для продолжения работы, авторизуйтесь,'
            ' используя логин и пароль, указанный '
            'при регистрации на сайте курса!',
            reply_markup=kb.main_kb(),
        )


@bot.message_handler(func=lambda message: message.text == 'Авторизация🔑')
def login(message):
    """
    Функция принимает сообщение с main_kb, запрашивает сообщением
    логин пользователя, ожидает ввода данных пользователем
    """
    temp_data[message.chat.id] = {}
    keyboard = telebot.types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id,
        'Введите логин, указанный при регистрации на сайте.',
        reply_markup=keyboard,
    )
    bot.register_next_step_handler(message, password)


def password(message):
    """
    Функция принимает логин пользователя в виде сообщения,
    сохраняет его в словаре и запрашивает пароль.
    Ожидает ввода пароля.
    """
    bot.send_message(message.chat.id, 'Введите пароль:')
    bot.register_next_step_handler(message, check_autorization)
    temp_data[message.chat.id]['login'] = message.text


def check_autorization(message):
    """
    Функция принимает пароль в виде сообщения, сохраняет его в словарь,
    после этого осуществляет проверку логина и пароля с данными из api,
    при совпадении выдает клавиатуру действий пользователя,
    при не совпадении - сообщение с ошибкой.
    """
    credentials = temp_data.pop(message.chat.id, {})
    login_value = credentials.get('login', '')
    try:
        auth_result = authenticate_student(login_value, message.text)
    except (requests.RequestException, RuntimeError, ValueError):
        bot.send_message(
            message.chat.id,
            'Сервис авторизации временно недоступен. Попробуйте ещё раз.',
        )
        login(message)
        return

    if not auth_result.get('authenticated'):
        bot.send_message(
            message.chat.id,
            'Неправильно введены данные!',
        )
        login(message)
        return

    username = auth_result['username']
    user = User(chat_id=message.chat.id, name=username)
    user.save()
    if message.chat.id == TG_ID_ADMIN:
        admin_actions(message, user)
    else:
        bot.send_message(
            message.chat.id,
            f'Привет, {username}!',
            reply_markup=kb.user_kb(),
        )


@bot.message_handler(func=lambda message: message.text == 'Пинг ⚾')
def button_ping(message):
    """
    Действия бота при нажатии кнопки 'Пинг ⚾'

    Эта кнопка нужна для того, чтобы проверить, что бот работает.
    Если он работает, он пишет пользователю 'Понг' на его нажатие
    кнопки 'Пинг'.
    """
    bot.send_message(message.chat.id, 'Понг ⚾')


@bot.message_handler(
    func=lambda message: message.text == 'Пропустить занятие 💤')
def skip_lesson_buttons(message):
    """
    Функция принимает с клавиатуры user_kb сообщение о пропуске занятия(й) и
    выдаёт клавиатуру выбора количества занятий, которые пользователь желает
    пропустить.
    """
    bot.send_message(
        message.chat.id,
        'Сколько занятий хотите пропустить?',
        reply_markup=kb.skip_lesson_kb(),
    )


@bot.message_handler(
    func=lambda message: message.text in ['1 💤', '2 💤💤', '3 💤💤💤']
)
def confirmation_skip_lesson(message):
    """
    Принимает данные с клавиатуры skip_lesson_kb, занося данные
    о пропуске занятия(й) в словарь number_of_passes с ключом
    'lessons'. Также запрашивает подтверждение пользователя о
    пропуске занятия(й).
    """
    bot.send_message(
        message.chat.id,
        'Точно хотите пропустить занятие(я)?',
        reply_markup=kb.skip_lesson_kb2(),
    )
    if message.text == '1 💤':
        number_of_passes['lessons'] = 1
    elif message.text == '2 💤💤':
        number_of_passes['lessons'] = 2
    elif message.text == '3 💤💤💤':
        number_of_passes['lessons'] = 3


@bot.message_handler(func=lambda message: message.text == 'Да 👍')
def pass_lesson(message):
    """
    Действия бота при подтверждении пропуска занятий пользователем
    по кнопке 'Да 👍'.

    На сайт отправляется post запрос(ы) (в зависимости от
    количества пропусков) с именем пользователя и датой пропуска
    занятия(й). Также админу присылается уведомление о пропуске
    занятия(й) определённым пользователем, а пользователю бот
    сообщает об успешной записи количества пропусков занятий и
    высылает ему клавиатуру user_kb.
    """
    api_missing = os.getenv('API_MISSING')
    user = User.select().where(User.chat_id == message.chat.id).first()
    date = datetime.date.today() + datetime.timedelta(days=1)
    for _ in range(number_of_passes['lessons']):
        requests.post(
            api_missing,
            data={'username': user.name, 'date': date.strftime('%Y-%m-%d')},
            timeout=5,
        )
        date += datetime.timedelta(days=2)
    bot.send_message(
        TG_ID_ADMIN,
        f'❗️ Ученик {user.name} пропускает'
        f' {number_of_passes["lessons"]} занятие(я) ❗️',
    )
    bot.send_message(
        message.chat.id,
        'Ваше количество пропусков занятий успешно записано!',
        reply_markup=kb.user_kb(),
    )


@bot.message_handler(func=lambda message: message.text == 'Нет 👎')
def no_pass_lesson(message):
    """
    Если пользователь передумал и отказался пропускать занятие(я),
    нажав на кнопку 'Нет 👎', ему бот отсылает сообщение и высылает
    клавиатуру user_kb.
    """
    bot.send_message(
        message.chat.id,
        'Хорошо, что вы отказались пропускать занятие(я) 👍👍👍',
        reply_markup=kb.user_kb(),
    )


@bot.message_handler(func=lambda message: message.text == 'Оплата 💰')
def pay(message):
    """
    Функция обрабатывает запрос на оплату от пользователя, проверяет сумму,
    которую необходимо оплатить, и отправляет пользователю ссылку для оплаты.

    Args:
        message: объект сообщения, содержащий информацию о пользователе и чате.

    Returns:
        None
    """
    user = User.select().where(User.chat_id == message.chat.id).first()
    amount = get_payment(user.name)['amount']
    if amount <= 0:
        bot.send_message(message.chat.id, 'Вы уже оплатили занятия!')
        return
    payment = get_payment_url(amount)
    bot.send_message(
        message.chat.id, f'Оплатите {amount} рублей, по ссылке: {payment[0]}'
    )
    pay_data[message.chat.id] = {
        'amount': amount,
        'payment_id': payment[1],
        'name': user.name,
    }


@bot.message_handler(func=lambda message: message.text == 'Твой собес 👨‍💻')
def check_category_interview_button(message):
    """
    Действия бота при нажатии кнопки 'Твой собес'.
    """
    chat_id = message.chat.id
    bot.send_message(chat_id, f'Выберите категорию вопросов:',
                     reply_markup=kb.check_category_interview())


@bot.message_handler(func=lambda message: message.text == 'Вопросы')
def interview_button(message):
    """
    Действия бота при нажатии кнопки 'Вопросы'.
    """
    chat_id = message.chat.id
    bot.send_message(chat_id, f'Выберите категорию вопросов:',
                     reply_markup=kb.category_kb())


@bot.message_handler(func=lambda message: message.text == 'AI Собес')
def interview_question_ai_assistant_button(message):
    """
    Действия бота при нажатии кнопки 'AI Собес'.
    """
    chat_id = message.chat.id

    amount_current_day = list(
        Interview.select().where(Interview.chat_id == chat_id,
                                 Interview.date == current_date())) or '0'
    if len(amount_current_day) >= 10:
        bot.send_message(chat_id,
                         'Вы израсходовали лимит на запросы. Попробуйте завтра!')
        return
    bot.send_message(chat_id, f'Выберите категорию',
                     reply_markup=kb.get_question_category())
    bot.register_next_step_handler(message, interview_get_question)


def interview_get_question(message):
    chat_id = message.chat.id
    category = message.text.replace('Р', 'P').replace('о', 'o').replace('O',
                                                                        'О')
    if category == 'Python':
        bot.send_message(chat_id, 'Укажите сложность вопроса:',
                         reply_markup=kb.difficulty_kb(symbol='—'))
        bot.register_next_step_handler(message, interview_get_question)
        return
    level = ''
    if '—' in category:
        level = category
        category = 'Python'
    questions = get_interview_question(category, level=level.replace('—', '-'))
    question = f'{questions[0]["title"]}'
    if category == 'Python':
        question += f' ({questions[0]["complexity"]})'
    keyboard = telebot.types.ReplyKeyboardRemove()
    bot.send_message(chat_id, f'Вопрос:\n{question}', reply_markup=keyboard)
    interview_question[chat_id] = question
    bot.register_next_step_handler(message,
                                   interview_check_ai_assistant_button)


def interview_check_ai_assistant_button(message):
    """
    Получает вопрос и ответ пользователя и отправляет эти данные на
    оценку (API).
    """
    chat_id = message.chat.id
    question = interview_question[chat_id]
    answer = message.text
    if question[-1] == ')' and question[-2].isdigit() and question[-3] == '(':
        question = question[:-4]

    msg = bot.send_message(chat_id, '⚙️ Ожидание...')
    result = check_interview_question(question, answer)
    interview = Interview(chat_id=chat_id)
    interview.save()

    amount_current_day = list(
        Interview.select().where(Interview.chat_id == chat_id,
                                 Interview.date == current_date())) or '0'
    request_text = 'запрос'
    left = 10 - len(amount_current_day)
    if 2 <= left <= 4:
        request_text += 'а'
    elif left > 4:
        request_text += 'ов'
    bot.edit_message_text(chat_id=chat_id,
                          message_id=msg.message_id,
                          text=f'Сегодня осталось {left} '
                               f'{request_text}!',
                          reply_markup=kb.next_ai_interview())

    keyboard = kb.user_kb()
    if message.chat.id == TG_ID_ADMIN:
        keyboard = kb.admin_kb()

    bot.send_message(chat_id, text=result,
                     reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == 'Python')
def interview_button_Python(message):
    """
    Действия бота при нажатии кнопки 'Python'.
    Вызывает следующую клавиатуру.
    """
    chat_id = message.chat.id
    bot.send_message(chat_id, 'Укажите сложность вопросов:',
                     reply_markup=kb.difficulty_kb())


@bot.message_handler(
    func=lambda message: message.text in ['1-3', '1-5', '1-7', '3-5', '5-7',
                                          '7-9'])
def interview_difficult_python(message):
    """
    Действия бота при выборе сложности вопросов уровня Python.
    """
    chat_id = message.chat.id
    interview_data[chat_id] = {
        'category': 'Python',
        'difficulty': message.text,
        'Python': True,
    }
    bot.send_message(chat_id,
                     'Укажите количество вопросов:',
                     reply_markup=kb.amount_question_kb())
    bot.register_next_step_handler(message, interview_question_amount)


@bot.message_handler(
    func=lambda message: message.text in ['HR’ские', 'Django', 'ООП'])
def interview_button_another(message):
    """
    Действия бота при нажатии кнопки 'HR', 'Django', 'ООП'.
    Уточняет количество вопросов, сохраняет chat_id в temp_data.
    """
    chat_id = message.chat.id
    interview_data[chat_id] = {
        'category': message.text,
        'Python': False,
    }
    bot.send_message(chat_id,
                     'Укажите количество вопросов:',
                     reply_markup=kb.amount_question_kb())
    bot.register_next_step_handler(message, interview_question_amount)


def interview_question_amount(message):
    """
    Действия бота после просьбы ввести количество вопросов.
    Отправляет запрос по api к сайту, для вывода списка вопросов и дальнейшей
    отправке боту.
    """
    chat_id = message.chat.id
    amount: str = message.text
    if amount.isdigit() and not (5 <= int(amount) <= 20):
        bot.send_message(chat_id,
                         '❌ Допустимое количество вопросов от 5 до 20')
        bot.register_next_step_handler(message, interview_question_amount)
        return
    category = interview_data[chat_id]['category']
    string = ''
    if interview_data[chat_id]['Python']:
        difficulty = interview_data[chat_id]['difficulty']
        data = get_questions(category, amount, difficulty)
    else:
        data = get_questions(category, amount)

    for k, i in enumerate(data):
        string += f'{k + 1}) {i["title"]}\n'

    keyboard = kb.user_kb()
    if message.chat.id == TG_ID_ADMIN:
        keyboard = kb.admin_kb()
    bot.send_message(chat_id,
                     f'Сгенерированные вопросы:\n{string}',
                     reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'next_ai')
def next_question_ai_interview(call):
    """
    Действия бота после нажатия кнопки '👉 Следующий вопрос'.
    Вызывает функцию interview_question_ai_assistant_button.
    """
    message = call.message
    interview_question_ai_assistant_button(message)


@bot.message_handler()
def unknown_command(message):
    """
    Обработчик неизвестной команды.
    """
    keyboard = kb.user_kb()
    if message.chat.id == TG_ID_ADMIN:
        keyboard = kb.admin_kb()
    bot.send_message(message.chat.id, '🧐 Я вас не понял...',
                     reply_markup=keyboard)
