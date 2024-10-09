"""
Модуль отвечает за создание таблиц базы данных посредством ORM PEEWEE
"""
import datetime

from peewee import *

db = SqliteDatabase('users.db')


class BaseModel(Model):
    """
    Базовая модель, от которой наследуются все остальные модели.

    Атрибуты:
        id (PrimaryKeyField): Уникальный идентификатор записи.
    """

    id = PrimaryKeyField(unique=True)

    class Meta:
        """
        Метакласс для определения базы данных.
        """

        database = db


class User(BaseModel):
    """
    Модель для хранения информации о пользователях.

    Атрибуты:
        chat_id (IntegerField): Уникальный идентификатор чата.
        name (CharField): Имя пользователя.
    """

    chat_id = IntegerField(unique=True)
    name = CharField()

    class Meta:
        """
        Метакласс для определения имени таблицы.
        """
        db_table = 'users'


class Application(BaseModel):
    """
    Модель для хранения информации о заявках.

    Атрибуты:
        id_application (IntegerField): Уникальный идентификатор заявки.
    """
    id_application = IntegerField(unique=True)

    class Meta:
        """
        Метакласс для определения имени таблицы.
        """
        db_table = 'applications'


class Review(BaseModel):
    """
    Модель для хранения информации об отзывах.

    Атрибуты:
        id_review (IntegerField): Уникальный идентификатор отзыва.
    """
    id_review = IntegerField(unique=True)

    class Meta:
        """
        Метакласс для определения имени таблицы.
        """
        db_table = 'reviews'


def current_date():
    return datetime.datetime.now().date()


class Interview(BaseModel):
    """
    Модель для хранения информации о запросах к сервису Твой Собес (GPT).

    Атрибуты:
        id_review (IntegerField): Уникальный идентификатор отзыва.
    """
    chat_id = IntegerField()
    date = DateField(default=current_date)

    class Meta:
        """
        Метакласс для определения имени таблицы.
        """
        db_table = 'interview'


db.create_tables([User, Application, Review, Interview])
