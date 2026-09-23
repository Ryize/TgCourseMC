import io
import types as pytypes
import unittest

import requests
from peewee import SqliteDatabase

from coursemc_client import CourseMCAPIError, CourseMCClient
from lesson_solutions import (
    LessonSolutionHandlers,
    LessonSolutionService,
    StaleSubmissionError,
)
from models import (
    AIReviewTracking,
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
        self.edit_text_error = None
        self.edit_markup_error = None

    def send_message(self, chat_id, text, reply_markup=None):
        message = pytypes.SimpleNamespace(message_id=self.next_message_id)
        self.next_message_id += 1
        self.messages.append((chat_id, text, reply_markup, message.message_id))
        return message

    def send_document(self, chat_id, document):
        self.documents.append((chat_id, document.name, document.read()))
        return pytypes.SimpleNamespace(message_id=self.next_message_id)

    def edit_message_reply_markup(self, **kwargs):
        if self.edit_markup_error:
            raise self.edit_markup_error
        self.edited_markups.append(kwargs)

    def edit_message_text(self, text, **kwargs):
        if self.edit_text_error:
            raise self.edit_text_error
        self.edited_texts.append((text, kwargs))

    def answer_callback_query(self, callback_id, text, show_alert=False):
        self.callback_answers.append((callback_id, text, show_alert))


class FakeClient:
    def __init__(self, pages=None, details=None):
        self.pages = list(pages or [])
        self.details = list(details or [])
        self.get_calls = []
        self.detail_calls = []
        self.download_calls = []
        self.review_calls = []
        self.review_error = None

    def get_solutions(self, cursor, teacher_username, limit=50):
        self.get_calls.append((cursor, teacher_username, limit))
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page

    def get_solution(self, solution_id):
        self.detail_calls.append(solution_id)
        detail = (
            self.details.pop(0)
            if self.details else CourseMCAPIError(404, 'old API')
        )
        if callable(detail):
            detail = detail()
        if isinstance(detail, Exception):
            raise detail
        return detail

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


MISSING = object()


def solution(submission_id=127, files=1, attempt=1, ai_review=MISSING):
    result = {
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
    if ai_review is not MISSING:
        result['ai_review'] = ai_review
    return result


def review(status, feedback='Проверьте обработку пустого списка.', **extra):
    result = {
        'status': status,
        'status_display': status,
        'feedback': feedback,
        'issue_count': 1,
        'source_summary': 'Проверены: solution.py.',
        'error': None,
        'reviewed_at': '2026-08-24T12:31:00+03:00',
    }
    result.update(extra)
    return result


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

    def make_service(self, pages, details=None):
        client = FakeClient(pages, details)
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

    def test_ready_ai_review_is_shown_only_in_teacher_notification(self):
        service, client = self.make_service([
            page(solution(ai_review=review('ready'))),
        ])

        service.poll_once()

        message = self.bot.messages[0][1]
        self.assertIn('Предварительная рекомендация ИИ', message)
        self.assertIn('Проверьте обработку пустого списка.', message)
        self.assertEqual(client.detail_calls, [])
        self.assertEqual(AIReviewTracking.get().status, 'ready')

    def test_ready_review_without_feedback_does_not_mean_no_errors(self):
        service, _ = self.make_service([
            page(solution(ai_review=review(
                'ready',
                feedback=None,
                issue_count=0,
            ))),
        ])

        service.poll_once()

        message = self.bot.messages[0][1]
        self.assertIn('Это не означает, что в работе нет ошибок.', message)
        self.assertNotIn('явных ошибок не найдено', message)
        self.assertNotIn('Существенных замечаний: 0', message)

    def test_pending_ai_review_updates_existing_message_after_cursor_is_saved(self):
        pending = solution(ai_review=review('pending', feedback=None))
        ready = solution(ai_review=review('ready'))
        service, client = self.make_service(
            [page(pending), page(cursor=127)],
            [ready],
        )

        service.poll_once()

        self.assertEqual(BotState.get().value, '127')
        self.assertEqual(len(self.bot.messages), 1)
        self.assertIn('Рекомендация готовится', self.bot.messages[0][1])
        self.assertNotIn('Существенных замечаний:', self.bot.messages[0][1])
        self.assertFalse(self.bot.edited_texts)

        service.poll_once()

        self.assertEqual(client.detail_calls, [42])
        self.assertEqual(len(self.bot.messages), 1)
        self.assertEqual(len(self.bot.documents), 1)
        self.assertIn(
            'Проверьте обработку пустого списка.',
            self.bot.edited_texts[-1][0],
        )
        self.assertEqual(AIReviewTracking.get().status, 'ready')

    def test_failed_telegram_edit_retries_without_losing_ai_recommendation(self):
        pending = solution(ai_review=review('pending', feedback=None))
        ready = solution(ai_review=review('ready'))
        service, client = self.make_service(
            [page(pending), page(cursor=127), page(cursor=127)],
            [ready, ready],
        )
        service.poll_once()
        self.bot.edit_text_error = RuntimeError('Telegram temporarily failed')

        service.poll_once()

        self.assertEqual(BotState.get().value, '127')
        self.assertEqual(AIReviewTracking.get().status, 'pending')
        self.assertFalse(self.bot.edited_texts)

        self.bot.edit_text_error = None
        service.poll_once()

        self.assertEqual(client.detail_calls, [42, 42])
        self.assertEqual(AIReviewTracking.get().status, 'ready')
        self.assertIn('Проверьте обработку', self.bot.edited_texts[-1][0])
        self.assertEqual(len(self.bot.messages), 1)

    def test_interrupted_first_delivery_updates_existing_message_on_retry(self):
        pending = solution(ai_review=review('pending', feedback=None))
        ready = solution(ai_review=review('ready'))
        service, _ = self.make_service([page(pending), page(ready)])
        self.bot.edit_markup_error = RuntimeError('Telegram temporarily failed')

        with self.assertRaises(RuntimeError):
            service.poll_once()

        self.assertEqual(len(self.bot.messages), 1)
        self.assertFalse(BotState.select().exists())
        self.assertFalse(AIReviewTracking.select().exists())
        self.bot.edit_markup_error = None

        service.poll_once()

        self.assertEqual(BotState.get().value, '127')
        self.assertEqual(len(self.bot.messages), 1)
        self.assertEqual(len(self.bot.documents), 1)
        self.assertIn('Проверьте обработку', self.bot.edited_texts[-1][0])
        self.assertEqual(AIReviewTracking.get().status, 'ready')

    def test_detail_refresh_runs_after_saving_new_queue_cursor(self):
        pending = solution(ai_review=review('pending', feedback=None))
        seen_cursors = []

        def detail():
            seen_cursors.append(BotState.get().value)
            return solution(ai_review=review('ready'))

        service, _ = self.make_service(
            [page(pending), page(cursor=128)],
            [detail],
        )
        service.poll_once()
        service.poll_once()

        self.assertEqual(seen_cursors, ['128'])

    def test_all_teachers_receive_new_work_before_ai_detail_refresh(self):
        TeacherIdentity.create(
            telegram_user_id=2002,
            django_username='second_teacher',
        )
        pending = solution(ai_review=review('pending', feedback=None))
        second_teacher_work = solution(submission_id=200)
        seen_states = []

        def detail():
            seen_states.append((
                BotState.get(
                    BotState.key == 'lesson-solutions-cursor:second_teacher'
                ).value,
                len(self.bot.messages),
            ))
            return solution(ai_review=review('ready'))

        service, _ = self.make_service(
            [
                page(pending),
                page(cursor=0),
                page(cursor=127),
                page(second_teacher_work),
            ],
            [detail],
        )
        service.poll_once()
        service.poll_once()

        self.assertEqual(seen_states, [('200', 2)])

    def test_ai_update_preserves_a_completed_teacher_review(self):
        pending = solution(ai_review=review('pending', feedback=None))
        ready = solution(ai_review=review('ready'))
        service, client = self.make_service(
            [page(pending), page(cursor=127)],
            [ready, ready],
        )
        service.poll_once()
        notification = SolutionNotification.get()
        service.accept(1001, notification.id)

        service.poll_once()

        self.assertEqual(len(client.review_calls), 1)
        self.assertIn('Проверьте обработку', self.bot.edited_texts[-1][0])
        self.assertIn('✅ Принято', self.bot.edited_texts[-1][0])
        self.assertIsNone(self.bot.edited_texts[-1][1]['reply_markup'])
        self.assertEqual(AIReviewTracking.get().status, 'ready')

    def test_partial_ai_review_clearly_requires_manual_check(self):
        partial = review(
            'partial',
            feedback=None,
            source_summary='Проверены: solution.py. Не проверен report.pdf.',
        )
        service, _ = self.make_service([
            page(solution(ai_review=partial)),
        ])

        service.poll_once()

        message = self.bot.messages[0][1]
        self.assertIn('проверка неполная', message)
        self.assertIn('Нужна ручная проверка всех файлов.', message)
        self.assertIn('Не проверен report.pdf.', message)
        self.assertIn('Это не означает, что в работе нет ошибок.', message)

    def test_failed_or_unsupported_ai_review_requires_manual_check(self):
        for status in ('failed', 'unsupported'):
            with self.subTest(status=status):
                self.setUp()
                service, _ = self.make_service([
                    page(solution(ai_review=review(
                        status,
                        feedback=None,
                        error='Сервис временно недоступен.',
                    ))),
                ])

                service.poll_once()

                message = self.bot.messages[0][1]
                self.assertIn('ИИ-рекомендация недоступна.', message)
                self.assertIn('Требуется ручная проверка', message)
                self.assertIn('Сервис временно недоступен.', message)

    def test_newer_submission_never_updates_an_old_notification(self):
        first = solution(
            submission_id=127,
            attempt=1,
            ai_review=review('pending', feedback=None),
        )
        second = solution(
            submission_id=128,
            attempt=2,
            ai_review=review('pending', feedback=None),
        )
        detail_for_new_attempt = solution(
            submission_id=128,
            attempt=2,
            ai_review=review('ready', 'Это новая попытка.'),
        )
        service, client = self.make_service(
            [page(first), page(second)],
            [detail_for_new_attempt],
        )

        service.poll_once()
        service.poll_once()

        old_notification = SolutionNotification.get(
            SolutionNotification.submission_id == 127
        )
        old_tracking = AIReviewTracking.get(
            AIReviewTracking.notification == old_notification
        )
        self.assertEqual(client.detail_calls, [])
        self.assertEqual(old_tracking.status, 'stale')
        self.assertEqual(old_notification.status, 'superseded')
        self.assertIn('Отправлена новая попытка', self.bot.edited_texts[-1][0])
        self.assertIsNone(self.bot.edited_texts[-1][1]['reply_markup'])
        self.assertEqual(SolutionNotification.select().count(), 2)
        self.assertNotIn('Это новая попытка.', self.bot.messages[0][1])

    def test_old_button_cannot_review_a_newer_attempt_not_yet_polled(self):
        first = solution(submission_id=127)
        newer = solution(submission_id=128, attempt=2)
        service, client = self.make_service([page(first)], [newer])
        service.poll_once()
        notification = SolutionNotification.get()

        with self.assertRaises(StaleSubmissionError):
            service.accept(1001, notification.id)

        self.assertFalse(client.review_calls)
        self.assertEqual(SolutionNotification.get().status, 'superseded')
        self.assertIn('новая попытка', self.bot.edited_texts[-1][0])

    def test_repeated_old_page_cannot_reactivate_superseded_buttons(self):
        first = solution(submission_id=127)
        newer = solution(submission_id=128, attempt=2)
        service, _ = self.make_service([page(first), page(newer)])
        service.poll_once()
        service.poll_once()
        old_notification = SolutionNotification.get(
            SolutionNotification.submission_id == 127
        )
        newer_notification = SolutionNotification.get(
            SolutionNotification.submission_id == 128
        )
        markup_count = len(self.bot.edited_markups)

        service._deliver_submission(self.teacher, first)

        self.assertEqual(len(self.bot.edited_markups), markup_count)
        self.assertEqual(
            SolutionNotification.get_by_id(old_notification.id).status,
            'superseded',
        )
        self.assertEqual(
            SolutionNotification.get_by_id(newer_notification.id).status,
            'pending',
        )

    def test_new_attempt_during_comment_entry_prevents_review(self):
        first = solution(submission_id=127)
        newer = solution(submission_id=128, attempt=2)
        service, client = self.make_service(
            [page(first)],
            [first, newer],
        )
        service.poll_once()
        notification = SolutionNotification.get()
        service.request_revision_comment(1001, notification.id)

        with self.assertRaises(StaleSubmissionError):
            service.submit_revision_comment(1001, 'Исправьте код')

        self.assertFalse(client.review_calls)
        self.assertFalse(PendingSolutionReview.select().exists())
        self.assertEqual(SolutionNotification.get().status, 'superseded')

    def test_legacy_queue_without_ai_review_remains_supported(self):
        service, client = self.make_service([page(solution()), page(cursor=127)])

        service.poll_once()
        service.poll_once()

        self.assertNotIn('🤖', self.bot.messages[0][1])
        self.assertFalse(AIReviewTracking.select().exists())
        self.assertEqual(client.detail_calls, [])

    def test_missing_detail_endpoint_does_not_break_pending_delivery(self):
        pending = solution(ai_review=review('pending', feedback=None))
        service, client = self.make_service(
            [page(pending), page(cursor=127)],
            [CourseMCAPIError(404, 'not found')],
        )

        service.poll_once()
        service.poll_once()

        self.assertEqual(BotState.get().value, '127')
        self.assertEqual(client.detail_calls, [42])
        self.assertEqual(AIReviewTracking.get().status, 'detail_unavailable')
        self.assertIn('Требуется ручная проверка', self.bot.edited_texts[-1][0])

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
    def test_get_solution_uses_protected_detail_endpoint(self):
        response = FakeHTTPResponse(200, {'id': 42, 'submission_id': 127})
        session = FakeHTTPSession(response)
        client = CourseMCClient(
            'https://coursemc.ru/api/v1',
            'very-secret-token',
            session=session,
        )

        self.assertEqual(client.get_solution(42)['id'], 42)
        self.assertEqual(
            session.last_url,
            'https://coursemc.ru/api/v1/bot/lesson-solutions/42/',
        )
        self.assertNotIn('very-secret-token', session.last_url)

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
