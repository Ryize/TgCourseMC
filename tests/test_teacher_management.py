import datetime as dt
import os
import types as pytypes
import unittest
from unittest.mock import patch

from peewee import SqliteDatabase

from models import (
    ALL_MODELS,
    OwnerFlow,
    TeacherIdentity,
    TeacherInvite,
)
from teacher_management import (
    TeacherManagementService,
    TeacherManagementStore,
)


class FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))
        return pytypes.SimpleNamespace(message_id=len(self.messages))

    def get_me(self):
        return pytypes.SimpleNamespace(username='CourseMC_bot')


class FakeClient:
    def __init__(self):
        self.get_calls = []

    def get_solutions(self, cursor, teacher_username, limit=50):
        self.get_calls.append((cursor, teacher_username, limit))
        return {'count': 0, 'next_cursor': cursor, 'results': []}


def message(user_id, text):
    return pytypes.SimpleNamespace(
        text=text,
        chat=pytypes.SimpleNamespace(id=user_id),
        from_user=pytypes.SimpleNamespace(id=user_id),
    )


class TeacherManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})
        cls.database.bind(ALL_MODELS)
        cls.database.connect()
        cls.database.create_tables(ALL_MODELS)

    @classmethod
    def tearDownClass(cls):
        cls.database.drop_tables(ALL_MODELS)
        cls.database.close()

    def setUp(self):
        for model in reversed(ALL_MODELS):
            model.delete().execute()
        self.bot = FakeBot()
        self.client = FakeClient()
        self.store = TeacherManagementStore(owner_telegram_id=100)
        self.service = TeacherManagementService(
            self.bot,
            self.client,
            self.store,
        )

    def test_only_owner_can_open_management_menu(self):
        with self.assertRaises(PermissionError):
            self.service.send_menu(200, 200)

        self.service.send_menu(100, 100)

        self.assertIn('Управление преподавателями', self.bot.messages[-1][1])

    def test_owner_validates_teacher_and_invite_is_one_time(self):
        self.service.begin_add_teacher(100, 100)
        self.assertTrue(OwnerFlow.select().exists())

        with patch.dict(os.environ, {'TELEGRAM_BOT_USERNAME': 'CourseMC_bot'}):
            self.service.handle_owner_input(message(100, 'teacher_login'))

        self.assertEqual(self.client.get_calls, [(0, 'teacher_login', 1)])
        self.assertFalse(OwnerFlow.select().exists())
        invite_text = self.bot.messages[-1][1]
        token = invite_text.split('?start=teacher_', 1)[1].splitlines()[0]

        claimed = self.service.claim_start_payload(
            message(200, f'/start teacher_{token}')
        )

        self.assertTrue(claimed)
        identity = TeacherIdentity.get()
        self.assertEqual(identity.telegram_user_id, 200)
        self.assertEqual(identity.django_username, 'teacher_login')
        self.assertIsNotNone(TeacherInvite.get().used_at)

        self.service.claim_start_payload(message(300, f'/start teacher_{token}'))
        self.assertEqual(TeacherIdentity.select().count(), 1)
        self.assertIn('уже использована', self.bot.messages[-1][1])

    def test_expired_invite_cannot_be_claimed(self):
        token = self.store.create_invite('teacher_login', 100)
        invite = TeacherInvite.get()
        invite.expires_at = dt.datetime.now() - dt.timedelta(seconds=1)
        invite.save()

        self.service.claim_start_payload(message(200, f'/start teacher_{token}'))

        self.assertFalse(TeacherIdentity.select().exists())
        self.assertIn('истёк', self.bot.messages[-1][1])

    def test_owner_can_list_connected_teachers(self):
        TeacherIdentity.create(
            telegram_user_id=200,
            django_username='teacher_login',
        )

        self.service.send_overview(100, 100)

        self.assertIn('teacher_login', self.bot.messages[-1][1])
        self.assertIn('Telegram ID 200', self.bot.messages[-1][1])

    def test_cancel_clears_persistent_flow(self):
        self.service.begin_add_teacher(100, 100)

        self.service.handle_owner_input(message(100, '/cancel'))

        self.assertFalse(OwnerFlow.select().exists())
        self.assertIn('отменено', self.bot.messages[-1][1])


if __name__ == '__main__':
    unittest.main()
