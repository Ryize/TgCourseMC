"""
Модуль содержит клавиатуры, используемые в телеграм-боте.
"""

from telebot import types


class KeyboardMixin:
    """
    Класс содержит основные клавиатуры, используемые в боте.
    """

    @staticmethod
    def main_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру авторизации.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопкой "Авторизация🔑".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Авторизация🔑')
        kb.row(btn1)
        return kb

    @staticmethod
    def user_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру авторизации.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопкой "Авторизация🔑".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Оплата 💰')
        btn2 = types.KeyboardButton('Пропустить занятие 💤')
        btn3 = types.KeyboardButton('Пинг ⚾')
        btn4 = types.KeyboardButton('Твой собес 👨‍💻')
        kb.row(btn1, btn3)
        kb.row(btn2, btn4)
        return kb

    @staticmethod
    def skip_lesson_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру пропуска занятия или занятий.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопками "1 💤",
            "2 💤💤" и "3 💤💤💤".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton(' 1 💤')
        btn2 = types.KeyboardButton(' 2 💤💤')
        btn3 = types.KeyboardButton(' 3 💤💤💤')
        kb.row(btn1, btn2, btn3)
        return kb

    @staticmethod
    def skip_lesson_kb2() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру подтверждения пропуска занятия.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопками "Да 👍"
            и "Нет 👎".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Да 👍')
        btn2 = types.KeyboardButton('Нет 👎')
        kb.row(btn1, btn2)
        return kb

    @staticmethod
    def admin_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру администратора.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с кнопками "Заявки 📝",
            "Отправить сообщение всем 📣" и "Пинг ⚾".
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Заявки 📝')
        btn2 = types.KeyboardButton('Отправить сообщение всем 📣')
        btn3 = types.KeyboardButton('Пинг ⚾')
        btn4 = types.KeyboardButton('Твой собес 👨‍💻')
        btn5 = types.KeyboardButton('Расписание 📆')
        kb.row(btn1, btn3)
        kb.row(btn2, btn4)
        kb.row(btn5)
        return kb

    @staticmethod
    def check_category_interview() -> types.ReplyKeyboardMarkup:
        """
        Создает основную клавиатуру твой собес.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с 4 кнопками
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Вопросы')
        btn2 = types.KeyboardButton('AI Собес')
        kb.row(btn1, btn2)
        return kb

    @staticmethod
    def category_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает основную клавиатуру твой собес.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с 4 кнопками
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('HR’ские')
        btn2 = types.KeyboardButton('Python')
        btn3 = types.KeyboardButton('ООП')
        btn4 = types.KeyboardButton('Django')
        kb.row(btn1, btn2)
        kb.row(btn3, btn4)
        return kb

    @staticmethod
    def difficulty_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает основную клавиатуру твой собес.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с 6 кнопками
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('1-3')
        btn2 = types.KeyboardButton('1-5')
        btn3 = types.KeyboardButton('1-7')
        btn4 = types.KeyboardButton('3-5')
        btn5 = types.KeyboardButton('5-7')
        btn6 = types.KeyboardButton('7-9')
        kb.row(btn1, btn2, btn3)
        kb.row(btn4, btn5, btn6)
        return kb

    @staticmethod
    def amount_question_kb() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру для выбора количества вопросов.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с 4 кнопками
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('5')
        btn2 = types.KeyboardButton('10')
        kb.row(btn1, btn2)
        return kb

    @staticmethod
    def weekday_buttons() -> types.ReplyKeyboardMarkup:
        """
        Создает клавиатуру для выбора количества вопросов.

        Returns:
            types.ReplyKeyboardMarkup: Клавиатура с 4 кнопками
        """
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('Понедельник')
        btn2 = types.KeyboardButton('Вторник')
        btn3 = types.KeyboardButton('Среда')
        btn4 = types.KeyboardButton('Четверг')
        btn5 = types.KeyboardButton('Пятница')
        btn6 = types.KeyboardButton('Суббота')
        btn7 = types.KeyboardButton('Воскресенье')
        kb.row(btn1, btn2, btn3)
        kb.row(btn4, btn5, btn6)
        kb.row(btn7)
        return kb

    @staticmethod
    def next_ai_interview() -> types.InlineKeyboardMarkup:
        """
        Создает Inline клавиатуру для перехода к следующему вопросу.

        Returns:
            types.InlineKeyboardMarkup: Клавиатура с 1 кнопкой
        """
        kb = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton(text='👉 Следующий вопрос',
                                          callback_data='next_ai')
        kb.row(btn1)
        return kb
