"""
Модуль отвечает за создание таблиц базы данных посредством ORM PEEWEE
"""

from peewee import *

db = SqliteDatabase("users.db")


class BaseModel(Model):
    id = PrimaryKeyField(unique=True)

    class Meta:
        database = db


class User(BaseModel):
    chat_id = IntegerField(unique=True)
    name = CharField()

    class Meta:
        db_table = "users"


db.create_tables([User])
