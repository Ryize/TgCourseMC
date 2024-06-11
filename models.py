"""
Модуль отвечает за создание таблиц базы данных посредством ORM PEEWEE
"""

from peewee import *

db = SqliteDatabase("users.db")


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
        db_table = "users"


class Application(BaseModel):
    id_application = IntegerField(unique=True)

    class Meta:
        db_table = "applications"



class Review(BaseModel):
    id_review = IntegerField(unique=True)

    class Meta:
        db_table = "reviews"


db.create_tables([User, Application, Review])
