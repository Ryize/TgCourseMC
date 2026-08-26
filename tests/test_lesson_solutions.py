import io
import types as pytypes
import unittest

import requests
from peewee import SqliteDatabase

from coursemc_client import CourseMCAPIError, CourseMCClient
from lesson_solutions import LessonSolutionHandlers, LessonSolutionService
from models import (
    ALL_MODELS,
    BotState,
    PendingSolutionReview,
    ProcessedSubmission,
    SolutionNotification,
    TeacherIdentity,
)


class FakeBot:
    def __init__(self):
        self.next_message_id = 1
        self.messages = []
        self.documents = []
        self.edited_texts = []
        self.edited_markups = []
        self.callback_answers = []

    def send_message(self, chat_id, text, reply_markup=None):
        message = pytypes.SimpleNamespace(message_id=self.next_message_id)
        self.next_message_id += 1
        self.messages.append((chat_id, text, reply_markup, message.message_id))
        return message

    def send_document(self, chat_id, document):
        self.documents.append((chat_id, document.name, document.read()))
        return pytypes.SimpleNamespace(message_id=self.next_message_id)

    def edit_message_reply_markup(self, **kwargs):
        self.edited_markups.append(kwargs)

    def edit_message_text(self, text, **kwargs):
        self.edited_texts.append((text, kwargs))

    def answer_callback_query(self, callback_id, text, show_alert=False):
        self.callback_answers.append((callback_id, text, show_alert))


class FakeClient:
    def __init__(self, pages=None):
        self.pages = list(pages or [])
        self.get_calls = []
        self.download_calls = []
        self.review_calls = []
        self.review_error = None

    def get_solutions(self, cursor, teacher_username, limit=50):
        self.get_calls.append((cursor, teacher_username, limit))
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page

    def download_file(self, file_info):
        self.download_calls.append(file_info['id'])
        result = io.BytesIO(f'file-{file_info["id"]}'.encode())
        result.name = file_info['original_name']
        return result

    def review_solution(
        self,
        solution_id,
        username,
        status,
        teacher_comment='',
    ):
        self.review_calls.append(
            (solution_id, username, status, teacher_comment)
        )
        if self.review_error:
            raise self.review_error
        return {
            'id': solution_id,
            'status': status,
            'teacher_comment': teacher_comment,
            'reviewer_username': username,
            'reviewed_at': '2026-08-24T13:15:00+03:00',
        }


def solution(submission_id=127, files=1, attempt=1):
    return {
        'id': 42,
        'submission_id': submission_id,
        'attempt_number': attempt,
        'student': {
            'id': 18,
            'username': 'student_login',
            'display_name': 'Иван Иванов',
        },
        'group': {'id': 7, 'title': 'Питонисты'},
        'lesson': {'id': 55, 'number': 44, 'title': 'Функции. Практика'},
        'submitted_at': '2026-08-24T12:30:00+03:00',
        'files': [
            {
                'id': index,
                'original_name': f'solution-{index}.py',
                'size': 12,
                'download_url': f'https://example.test/files/{index}/',
            }
            for index in range(1, files + 1)
        ],
    }


def page(*solutions, cursor=None):
    if cursor is None:
        cursor = max((item['submission_id'] for item in solutions), default=0)
    return {
        'count': len(solutions),
        'next_cursor': cursor,
        'results': list(solutions),
    }


class LessonSolutionServiceTests(unittest.TestCase):
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
        self.teacher = TeacherIdentity.create(
            telegram_user_id=1001,
            django_username='teacher_login',
        )
        self.bot = FakeBot()

    def make_service(self, pages):
        client = FakeClient(pages)
        return LessonSolutionService(self.bot, client), client

    def deliver(self, files=1):
        service, client = self.make_service([page(solution(files=files))])
        service.poll_once()
        notification = SolutionNotification.get()
        return service, client, notification

    def test_receives_new_solution_and_saves_cursor(self):
        service, client = self.make_service([page(solution())])

        delivered = service.poll_once()

        self.assertEqual(delivered, 1)
        self.assertIn('Новое решение на проверку', self.bot.messages[0][1])
        self.assertIn('Иван Иванов', self.bot.messages[0][1])
        self.assertEqual(len(self.bot.documents), 1)
        self.assertTrue(ProcessedSubmission.select().exists())
        self.assertEqual(BotState.get().value, '127')
        self.assertEqual(client.get_calls, [(0, 'teacher_login', 50)])

    def test_processed_submission_is_not_notified_twice(self):
        repeated = solution()
        service, _ = self.make_service([page(repeated), page(repeated)])
        service.poll_once()
        service.poll_once()

        notification_messages = [
            item for item in self.bot.messages
            if item[1].startswith('Новое решение')
        ]
        self.assertEqual(len(notification_messages), 1)
        self.assertEqual(len(self.bot.documents), 1)

    def test_resubmission_with_new_submission_id_creates_notification(self):
        first = solution(submission_id=127, attempt=1)
        second = solution(submission_id=128, attempt=2)
        service, _ = self.make_service([page(first), page(second)])

        service.poll_once()
        service.poll_once()

        self.assertEqual(SolutionNotification.select().count(), 2)
        self.assertEqual(ProcessedSubmission.select().count(), 2)
        self.assertIn('Попытка: 2', self.bot.messages[1][1])

    def test_downloads_one_and_multiple_files(self):
        for count in (1, 3):
            with self.subTest(files=count):
                self.setUp()
                service, client = self.make_service([
                    page(solution(files=count))
                ])
                service.poll_once()
                self.assertEqual(len(self.bot.documents), count)
                self.assertEqual(
                    client.download_calls,
                    list(range(1, count + 1)),
                )
                self.assertEqual(SolutionNotification.get().files_sent, count)

    def test_accepts_solution_using_trusted_teacher_mapping(self):
        service, client, notification = self.deliver()

        result = service.accept(1001, notification.id)

        self.assertEqual(result, 'Решение принято.')
        self.assertEqual(
            client.review_calls,
            [(42, 'teacher_login', 'accepted', '')],
        )
        notification = SolutionNotification.get_by_id(notification.id)
        self.assertEqual(notification.status, 'accepted')
        self.assertIn('✅ Принято', self.bot.edited_texts[-1][0])

        service.accept(1001, notification.id)
        self.assertEqual(len(client.review_calls), 1)

    def test_returns_solution_for_revision_with_comment(self):
        service, client, notification = self.deliver()
        service.request_revision_comment(1001, notification.id)

        result = service.submit_revision_comment(
            1001,
            'Добавьте обработку пустого списка.',
        )

        self.assertEqual(result, 'Решение возвращено на доработку.')
        self.assertEqual(
            client.review_calls[-1],
            (
                42,
                'teacher_login',
                'needs_revision',
                'Добавьте обработку пустого списка.',
            ),
        )
        self.assertFalse(PendingSolutionReview.select().exists())
        self.assertIn('Добавьте обработку', self.bot.edited_texts[-1][0])

    def test_cancels_revision_comment_input(self):
        service, _, notification = self.deliver()
        service.request_revision_comment(1001, notification.id)

        cancelled = service.cancel_revision(1001, notification.id)

        self.assertTrue(cancelled)
        self.assertFalse(PendingSolutionReview.select().exists())
        self.assertEqual(SolutionNotification.get().status, 'pending')

    def test_other_teacher_cannot_use_notification(self):
        service, _, notification = self.deliver()
        TeacherIdentity.create(
            telegram_user_id=2002,
            django_username='other_teacher',
        )

        with self.assertRaises(PermissionError):
            service.accept(2002, notification.id)

    def test_api_403_is_shown_as_neutral_access_error_and_buttons_remain(self):
        service, client, notification = self.deliver()
        client.review_error = CourseMCAPIError(403, 'forbidden')
        handlers = LessonSolutionHandlers(self.bot, lambda: service)
        call = pytypes.SimpleNamespace(
            id='callback-1',
            data=f'ls:a:{notification.id}',
            from_user=pytypes.SimpleNamespace(id=1001),
            message=pytypes.SimpleNamespace(
                chat=pytypes.SimpleNamespace(id=1001),
                message_id=notification.message_id,
            ),
        )

        handlers.handle_callback(call)

        self.assertEqual(
            self.bot.callback_answers[-1][1],
            'У вас нет доступа к этому решению.',
        )
        self.assertEqual(SolutionNotification.get().status, 'pending')
        self.assertFalse(self.bot.edited_texts)

    def test_temporary_api_failure_does_not_advance_cursor(self):
        service, _ = self.make_service([
            requests.ConnectionError('temporary'),
            page(solution()),
        ])

        with self.assertRaises(requests.ConnectionError):
            service.poll_once()
        self.assertFalse(BotState.select().exists())

        service.poll_once()
        self.assertEqual(BotState.get().value, '127')

    def test_cursor_is_restored_by_new_service_instance(self):
        service, _ = self.make_service([page(solution())])
        service.poll_once()
        restarted_client = FakeClient([page(cursor=127)])
        restarted = LessonSolutionService(FakeBot(), restarted_client)

        restarted.poll_once()

        self.assertEqual(restarted_client.get_calls[0][0], 127)


class FakeHTTPResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.headers = {}

    def json(self):
        return self.payload


class FakeHTTPSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.last_url = None

    def get(self, url, **kwargs):
        self.last_url = url
        return self.response


class CourseMCClientTests(unittest.TestCase):
    def test_invalid_token_response_is_not_retried_or_exposed_in_url(self):
        response = FakeHTTPResponse(403, {'detail': 'forbidden'})
        session = FakeHTTPSession(response)
        client = CourseMCClient(
            'https://coursemc.ru/api/v1',
            'very-secret-token',
            session=session,
        )

        with self.assertRaises(CourseMCAPIError) as raised:
            client.get_solutions(0, 'teacher_login')

        self.assertEqual(raised.exception.status_code, 403)
        self.assertNotIn('very-secret-token', session.last_url)
        self.assertEqual(
            session.headers['X-CourseMC-Bot-Token'],
            'very-secret-token',
        )

    def test_rejects_cross_origin_download_before_sending_secret(self):
        session = FakeHTTPSession(FakeHTTPResponse(200, {}))
        client = CourseMCClient(
            'https://coursemc.ru/api/v1',
            'very-secret-token',
            session=session,
        )

        with self.assertRaises(CourseMCAPIError):
            client.download_file({
                'download_url': 'https://attacker.example/file/',
                'size': 10,
                'original_name': 'solution.py',
            })

        self.assertIsNone(session.last_url)


if __name__ == '__main__':
    unittest.main()
