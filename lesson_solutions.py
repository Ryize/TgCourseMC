"""CourseMC lesson-solution polling and Telegram review workflow."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
from typing import Any, Callable

import requests
from peewee import IntegrityError
from telebot import types

from coursemc_client import (
    CourseMCAPIError,
    FileTooLargeError,
    client_from_environment,
)
from models import (
    BotState,
    PendingSolutionReview,
    ProcessedSubmission,
    SolutionNotification,
    TeacherIdentity,
)


logger = logging.getLogger(__name__)
POLL_LIMIT = 50
_service: 'LessonSolutionService | None' = None


def _parse_datetime(value: str | dt.datetime | None) -> dt.datetime | None:
    if isinstance(value, dt.datetime) or value is None:
        return value
    try:
        return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


def format_course_date(value: str | dt.datetime | None) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return 'дата не указана'
    months = (
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
    )
    return (
        f'{parsed.day} {months[parsed.month - 1]} {parsed.year} г. '
        f'{parsed:%H:%M}'
    )


class LessonSolutionStore:
    """Peewee-backed durable state used by both polling and callbacks."""

    @staticmethod
    def sync_teachers_from_environment(raw_value: str | None = None) -> None:
        raw_value = raw_value if raw_value is not None else os.getenv(
            'COURSEMC_TEACHERS',
            '',
        )
        if not raw_value.strip():
            return
        try:
            mapping = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                'COURSEMC_TEACHERS должен содержать JSON'
            ) from exc
        if not isinstance(mapping, dict):
            raise RuntimeError('COURSEMC_TEACHERS должен быть JSON-объектом')

        for telegram_id, django_username in mapping.items():
            try:
                telegram_id = int(telegram_id)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    'В COURSEMC_TEACHERS ключами должны быть Telegram user ID'
                ) from exc
            django_username = str(django_username).strip()
            if not django_username:
                raise RuntimeError(
                    'В COURSEMC_TEACHERS логин преподавателя '
                    'не может быть пустым'
                )
            identity = TeacherIdentity.get_or_none(
                TeacherIdentity.telegram_user_id == telegram_id
            )
            try:
                if identity:
                    identity.django_username = django_username
                    identity.active = True
                    identity.save()
                else:
                    TeacherIdentity.create(
                        telegram_user_id=telegram_id,
                        django_username=django_username,
                    )
            except IntegrityError as exc:
                raise RuntimeError(
                    'Один Django-логин нельзя назначить двум '
                    'Telegram-аккаунтам'
                ) from exc

    @staticmethod
    def active_teachers() -> list[TeacherIdentity]:
        query = TeacherIdentity.select().where(
            TeacherIdentity.active == True  # noqa: E712
        )
        return list(query)

    @staticmethod
    def teacher_by_telegram_id(
        telegram_user_id: int,
    ) -> TeacherIdentity | None:
        return TeacherIdentity.get_or_none(
            (TeacherIdentity.telegram_user_id == telegram_user_id)
            & (TeacherIdentity.active == True)  # noqa: E712
        )

    @staticmethod
    def cursor(teacher: TeacherIdentity) -> int:
        state = BotState.get_or_none(
            BotState.key
            == f'lesson-solutions-cursor:{teacher.django_username}'
        )
        return int(state.value) if state else 0

    @staticmethod
    def save_cursor(teacher: TeacherIdentity, value: int) -> None:
        key = f'lesson-solutions-cursor:{teacher.django_username}'
        state, _ = BotState.get_or_create(
            key=key,
            defaults={'value': str(value)},
        )
        state.value = str(value)
        state.save()

    @staticmethod
    def is_processed(teacher: TeacherIdentity, submission_id: int) -> bool:
        return ProcessedSubmission.select().where(
            (ProcessedSubmission.teacher == teacher)
            & (ProcessedSubmission.submission_id == submission_id)
        ).exists()

    @staticmethod
    def mark_processed(teacher: TeacherIdentity, submission_id: int) -> None:
        ProcessedSubmission.get_or_create(
            teacher=teacher,
            submission_id=submission_id,
        )

    @staticmethod
    def notification(
        teacher: TeacherIdentity,
        submission_id: int,
    ) -> SolutionNotification | None:
        return SolutionNotification.get_or_none(
            (SolutionNotification.teacher == teacher)
            & (SolutionNotification.submission_id == submission_id)
        )

    @staticmethod
    def notification_for_action(
        teacher: TeacherIdentity,
        notification_id: int,
    ) -> SolutionNotification | None:
        return SolutionNotification.get_or_none(
            (SolutionNotification.teacher == teacher)
            & (SolutionNotification.id == notification_id)
        )

    @staticmethod
    def pending_for_teacher(
        teacher: TeacherIdentity,
    ) -> PendingSolutionReview | None:
        return PendingSolutionReview.get_or_none(
            PendingSolutionReview.teacher == teacher
        )


class LessonSolutionService:
    def __init__(
        self,
        bot: Any,
        client: Any,
        store: LessonSolutionStore | None = None,
    ):
        self.bot = bot
        self.client = client
        self.store = store or LessonSolutionStore()

    def poll_once(self) -> int:
        delivered = 0
        for teacher in self.store.active_teachers():
            delivered += self.poll_teacher(teacher)
        return delivered

    def poll_teacher(self, teacher: TeacherIdentity) -> int:
        cursor = self.store.cursor(teacher)
        page = self.client.get_solutions(
            cursor,
            teacher.django_username,
            limit=POLL_LIMIT,
        )
        results = page.get('results') or []
        for solution in results:
            submission_id = int(solution['submission_id'])
            if self.store.is_processed(teacher, submission_id):
                continue
            self._deliver_submission(teacher, solution)

        next_cursor = int(page.get('next_cursor', cursor))
        self.store.save_cursor(teacher, next_cursor)
        return len(results)

    def _deliver_submission(
        self,
        teacher: TeacherIdentity,
        solution: dict[str, Any],
    ) -> None:
        submission_id = int(solution['submission_id'])
        notification = self.store.notification(teacher, submission_id)
        if notification is None:
            message_text = self._notification_text(solution)
            sent = self.bot.send_message(
                teacher.telegram_user_id,
                message_text,
                reply_markup=self._review_keyboard_placeholder(),
            )
            notification = SolutionNotification.create(
                teacher=teacher,
                submission_id=submission_id,
                solution_id=int(solution['id']),
                chat_id=teacher.telegram_user_id,
                message_id=sent.message_id,
                message_text=message_text,
            )
            self.bot.edit_message_reply_markup(
                chat_id=notification.chat_id,
                message_id=notification.message_id,
                reply_markup=self.review_keyboard(notification.id),
            )
        else:
            # Reapply the real keyboard after an interrupted first delivery.
            self.bot.edit_message_reply_markup(
                chat_id=notification.chat_id,
                message_id=notification.message_id,
                reply_markup=self.review_keyboard(notification.id),
            )

        files = solution.get('files') or []
        remaining_files = files[notification.files_sent:]
        for index, file_info in enumerate(
            remaining_files,
            start=notification.files_sent,
        ):
            try:
                document = self.client.download_file(file_info)
            except FileTooLargeError:
                self.bot.send_message(
                    notification.chat_id,
                    f'⚠️ Файл «{file_info.get("original_name", "без имени")}» '
                    'слишком большой для отправки в Telegram.',
                )
            else:
                try:
                    self.bot.send_document(notification.chat_id, document)
                finally:
                    document.close()
            notification.files_sent = index + 1
            notification.save()

        notification.delivered = True
        notification.save()
        self.store.mark_processed(teacher, submission_id)

    @staticmethod
    def _notification_text(solution: dict[str, Any]) -> str:
        student = solution.get('student') or {}
        group = solution.get('group') or {}
        lesson = solution.get('lesson') or {}
        display_name = (
            student.get('display_name')
            or student.get('username')
            or 'Не указан'
        )
        username = student.get('username') or 'не указан'
        return (
            'Новое решение на проверку\n\n'
            f'Ученик: {display_name} (@{username})\n'
            f'Группа: {group.get("title") or "Не указана"}\n'
            f'Урок: {lesson.get("number", "—")}. '
            f'{lesson.get("title") or "Без названия"}\n'
            f'Попытка: {solution.get("attempt_number", "—")}\n'
            f'Отправлено: {format_course_date(solution.get("submitted_at"))}'
        )

    @staticmethod
    def _review_keyboard_placeholder() -> types.InlineKeyboardMarkup:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton(
                '⏳ Подготовка…',
                callback_data='ls:wait',
            )
        )
        return keyboard

    @staticmethod
    def review_keyboard(notification_id: int) -> types.InlineKeyboardMarkup:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.row(
            types.InlineKeyboardButton(
                '✅ Принять',
                callback_data=f'ls:a:{notification_id}',
            ),
            types.InlineKeyboardButton(
                '🛠 На доработку',
                callback_data=f'ls:r:{notification_id}',
            ),
        )
        return keyboard

    @staticmethod
    def cancel_keyboard(notification_id: int) -> types.InlineKeyboardMarkup:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton(
                'Отмена',
                callback_data=f'ls:c:{notification_id}',
            )
        )
        return keyboard

    def accept(self, telegram_user_id: int, notification_id: int) -> str:
        teacher, notification = self._authorized_notification(
            telegram_user_id,
            notification_id,
        )
        if notification.status != 'pending':
            self._edit_reviewed_notification(notification)
            return 'Решение уже проверено.'
        result = self.client.review_solution(
            notification.solution_id,
            teacher.django_username,
            'accepted',
            '',
        )
        self._save_review_result(notification, result, 'accepted', '')
        self._finish_pending_review(notification)
        self._edit_reviewed_notification(notification)
        return 'Решение принято.'

    def request_revision_comment(
        self,
        telegram_user_id: int,
        notification_id: int,
    ) -> PendingSolutionReview:
        teacher, notification = self._authorized_notification(
            telegram_user_id,
            notification_id,
        )
        if notification.status != 'pending':
            self._edit_reviewed_notification(notification)
            raise AlreadyReviewedError('Решение уже проверено.')
        pending = self.store.pending_for_teacher(teacher)
        if pending is None:
            pending = PendingSolutionReview.create(
                teacher=teacher,
                notification=notification,
            )
        else:
            pending.notification = notification
            pending.prompt_message_id = None
            pending.save()
        prompt = self.bot.send_message(
            notification.chat_id,
            'Напишите комментарий для ученика:',
            reply_markup=self.cancel_keyboard(notification.id),
        )
        pending.prompt_message_id = prompt.message_id
        pending.save()
        return pending

    def cancel_revision(
        self,
        telegram_user_id: int,
        notification_id: int,
    ) -> bool:
        teacher, notification = self._authorized_notification(
            telegram_user_id,
            notification_id,
        )
        pending = self.store.pending_for_teacher(teacher)
        if pending is None or pending.notification_id != notification.id:
            return False
        pending.delete_instance()
        return True

    def has_pending_comment(self, telegram_user_id: int) -> bool:
        teacher = self.store.teacher_by_telegram_id(telegram_user_id)
        return bool(teacher and self.store.pending_for_teacher(teacher))

    def submit_revision_comment(
        self,
        telegram_user_id: int,
        comment: str,
    ) -> str:
        teacher = self.store.teacher_by_telegram_id(telegram_user_id)
        if teacher is None:
            raise PermissionError('Telegram-аккаунт не назначен преподавателю')
        pending = self.store.pending_for_teacher(teacher)
        if pending is None:
            raise LookupError('Нет ожидающего комментария')
        comment = comment.strip()
        if not comment:
            raise ValueError('Комментарий не может быть пустым')

        notification = pending.notification
        result = self.client.review_solution(
            notification.solution_id,
            teacher.django_username,
            'needs_revision',
            comment,
        )
        self._save_review_result(
            notification,
            result,
            'needs_revision',
            comment,
        )
        self._finish_pending_review(notification)
        self._edit_reviewed_notification(notification)
        return 'Решение возвращено на доработку.'

    def _authorized_notification(
        self,
        telegram_user_id: int,
        notification_id: int,
    ) -> tuple[TeacherIdentity, SolutionNotification]:
        teacher = self.store.teacher_by_telegram_id(telegram_user_id)
        if teacher is None:
            raise PermissionError('Telegram-аккаунт не назначен преподавателю')
        notification = self.store.notification_for_action(
            teacher,
            notification_id,
        )
        if notification is None:
            raise PermissionError('Уведомление недоступно этому преподавателю')
        return teacher, notification

    @staticmethod
    def _save_review_result(
        notification: SolutionNotification,
        result: dict[str, Any],
        fallback_status: str,
        fallback_comment: str,
    ) -> None:
        notification.status = result.get('status') or fallback_status
        notification.teacher_comment = result.get(
            'teacher_comment',
            fallback_comment,
        )
        notification.reviewer_username = result.get('reviewer_username', '')
        notification.reviewed_at = _parse_datetime(result.get('reviewed_at'))
        notification.save()

    def _finish_pending_review(
        self,
        notification: SolutionNotification,
    ) -> None:
        pending = PendingSolutionReview.get_or_none(
            PendingSolutionReview.notification == notification
        )
        if pending is None:
            return
        if pending.prompt_message_id:
            try:
                self.bot.edit_message_reply_markup(
                    chat_id=notification.chat_id,
                    message_id=pending.prompt_message_id,
                    reply_markup=None,
                )
            except Exception as exc:
                logger.warning(
                    'Could not remove finished review prompt markup: %s',
                    type(exc).__name__,
                )
        pending.delete_instance()

    def _edit_reviewed_notification(
        self,
        notification: SolutionNotification,
    ) -> None:
        if notification.status == 'accepted':
            status_text = '✅ Принято'
        else:
            status_text = '🛠 Нужна доработка'
        details = [notification.message_text, '', status_text]
        if notification.reviewer_username:
            details.append(f'Проверил: {notification.reviewer_username}')
        if notification.reviewed_at:
            reviewed = format_course_date(notification.reviewed_at)
            details.append(f'Проверено: {reviewed}')
        if notification.teacher_comment:
            details.append(f'Комментарий: {notification.teacher_comment}')
        self.bot.edit_message_text(
            '\n'.join(details),
            chat_id=notification.chat_id,
            message_id=notification.message_id,
            reply_markup=None,
        )


class AlreadyReviewedError(Exception):
    pass


class LessonSolutionHandlers:
    def __init__(
        self,
        bot: Any,
        service_provider: Callable[[], LessonSolutionService],
    ):
        self.bot = bot
        self.service_provider = service_provider

    def pending_filter(self, message: Any) -> bool:
        try:
            service = self.service_provider()
            return service.has_pending_comment(message.from_user.id)
        except RuntimeError:
            return False

    def handle_comment(self, message: Any) -> None:
        service = self.service_provider()
        try:
            result = service.submit_revision_comment(
                message.from_user.id,
                message.text or '',
            )
        except ValueError:
            self.bot.send_message(
                message.chat.id,
                'Комментарий не может быть пустым.',
            )
        except CourseMCAPIError as exc:
            self._send_api_error(message.chat.id, exc)
        except requests.RequestException:
            self.bot.send_message(
                message.chat.id,
                'Сайт временно недоступен. Комментарий сохранён в сценарии — '
                'попробуйте отправить его ещё раз или нажмите «Отмена».',
            )
        else:
            self.bot.send_message(message.chat.id, result)

    def handle_callback(self, call: Any) -> None:
        parts = (call.data or '').split(':')
        if len(parts) != 3 or not parts[2].isdigit():
            self.bot.answer_callback_query(call.id, 'Кнопка устарела.')
            return
        action, notification_id = parts[1], int(parts[2])
        try:
            service = self.service_provider()
            if action == 'a':
                result = service.accept(call.from_user.id, notification_id)
            elif action == 'r':
                service.request_revision_comment(
                    call.from_user.id,
                    notification_id,
                )
                result = 'Жду комментарий.'
            elif action == 'c':
                cancelled = service.cancel_revision(
                    call.from_user.id,
                    notification_id,
                )
                result = (
                    'Ввод комментария отменён.'
                    if cancelled
                    else 'Сценарий уже завершён.'
                )
                if cancelled:
                    self.bot.edit_message_reply_markup(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        reply_markup=None,
                    )
            else:
                result = 'Кнопка устарела.'
        except AlreadyReviewedError as exc:
            result = str(exc)
        except PermissionError:
            result = 'У вас нет доступа к этому решению.'
        except CourseMCAPIError as exc:
            result = self._api_error_text(exc)
        except requests.RequestException:
            result = 'Сайт временно недоступен. Попробуйте ещё раз.'
        except RuntimeError:
            result = 'Интеграция CourseMC пока не настроена.'
        self.bot.answer_callback_query(call.id, result, show_alert=False)

    def _send_api_error(self, chat_id: int, exc: CourseMCAPIError) -> None:
        self.bot.send_message(chat_id, self._api_error_text(exc))

    @staticmethod
    def _api_error_text(exc: CourseMCAPIError) -> str:
        if exc.status_code == 403:
            return 'У вас нет доступа к этому решению.'
        if exc.status_code == 404:
            return 'Решение больше не найдено на сайте.'
        if exc.status_code == 400:
            return (
                'Не удалось применить решение. '
                'Проверьте комментарий и повторите.'
            )
        return 'Сайт временно недоступен. Попробуйте ещё раз.'


def get_service(bot: Any | None = None) -> LessonSolutionService:
    global _service
    if _service is None:
        if bot is None:
            from config import bot as configured_bot

            bot = configured_bot
        _service = LessonSolutionService(bot, client_from_environment())
    return _service


def register_lesson_solution_handlers(bot: Any) -> LessonSolutionHandlers:
    handlers = LessonSolutionHandlers(bot, lambda: get_service(bot))
    bot.message_handler(
        func=handlers.pending_filter,
        content_types=['text'],
    )(handlers.handle_comment)
    bot.callback_query_handler(
        func=lambda call: (call.data or '').startswith('ls:'),
    )(handlers.handle_callback)
    return handlers


def poll_lesson_solutions_forever(
    bot: Any,
    stop_event: threading.Event | None = None,
) -> None:
    interval = max(5, int(os.getenv('COURSEMC_SOLUTIONS_POLL_INTERVAL', '60')))
    store = LessonSolutionStore()
    try:
        store.sync_teachers_from_environment()
        service = get_service(bot)
    except RuntimeError as exc:
        logger.error('CourseMC lesson-solution polling is disabled: %s', exc)
        return
    if not store.active_teachers():
        logger.warning('CourseMC polling: no teacher mappings configured')
        return

    while stop_event is None or not stop_event.is_set():
        try:
            service.poll_once()
        except CourseMCAPIError as exc:
            logger.warning(
                'CourseMC API polling failed with HTTP %s',
                exc.status_code,
            )
        except requests.RequestException as exc:
            logger.warning(
                'CourseMC API polling temporarily failed: %s',
                type(exc).__name__,
            )
        except Exception:
            logger.exception('Unexpected lesson-solution polling error')
        if stop_event is not None:
            stop_event.wait(interval)
        else:
            threading.Event().wait(interval)
