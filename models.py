"""
Модуль отвечает за создание таблиц базы данных посредством ORM PEEWEE
"""
import datetime
import os

from peewee import *

db = SqliteDatabase(
    os.getenv('BOT_DATABASE_PATH', 'users.db'),
    pragmas={'journal_mode': 'wal', 'foreign_keys': 1},
)


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


class TeacherIdentity(BaseModel):
    """Trusted mapping from a Telegram account to a Django staff username."""

    telegram_user_id = BigIntegerField(unique=True)
    django_username = CharField(unique=True)
    active = BooleanField(default=True)

    class Meta:
        db_table = 'teacher_identities'


class BotState(BaseModel):
    """Persistent cursors and other small integration values."""

    key = CharField(unique=True)
    value = TextField()

    class Meta:
        db_table = 'bot_state'


class ProcessedSubmission(BaseModel):
    """Idempotency marker for a delivered submission notification."""

    teacher = ForeignKeyField(TeacherIdentity, on_delete='CASCADE')
    submission_id = BigIntegerField()
    processed_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        db_table = 'processed_lesson_submissions'
        indexes = ((('teacher', 'submission_id'), True),)


class SolutionNotification(BaseModel):
    """Telegram message and partial file-delivery progress for a submission."""

    teacher = ForeignKeyField(TeacherIdentity, on_delete='CASCADE')
    submission_id = BigIntegerField()
    solution_id = BigIntegerField()
    chat_id = BigIntegerField()
    message_id = BigIntegerField()
    message_text = TextField()
    files_sent = IntegerField(default=0)
    delivered = BooleanField(default=False)
    status = CharField(default='pending')
    teacher_comment = TextField(default='')
    reviewer_username = CharField(default='')
    reviewed_at = DateTimeField(null=True)

    class Meta:
        db_table = 'lesson_solution_notifications'
        indexes = ((('teacher', 'submission_id'), True),)


class PendingSolutionReview(BaseModel):
    """Persistent “waiting for revision comment” conversation state."""

    teacher = ForeignKeyField(
        TeacherIdentity,
        unique=True,
        on_delete='CASCADE',
    )
    notification = ForeignKeyField(SolutionNotification, on_delete='CASCADE')
    prompt_message_id = BigIntegerField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        db_table = 'pending_lesson_solution_reviews'


ALL_MODELS = [
    User,
    Application,
    Review,
    Interview,
    TeacherIdentity,
    BotState,
    ProcessedSubmission,
    SolutionNotification,
    PendingSolutionReview,
]

db.create_tables(ALL_MODELS)
