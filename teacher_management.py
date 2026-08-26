"""Owner-only Telegram workflow for teachers and learning-group assignments."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
from typing import Any, Callable

import requests
from peewee import IntegrityError
from telebot import types

from config import COURSEMC_OWNER_TELEGRAM_ID
from coursemc_client import CourseMCAPIError, client_from_environment
from models import OwnerFlow, TeacherIdentity, TeacherInvite, db


INVITE_TTL = dt.timedelta(days=2)
ADD_TEACHER_ACTION = 'add_teacher'


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class TeacherManagementStore:
    """Persistent state for owner conversations and one-time invites."""

    def __init__(self, owner_telegram_id: int = COURSEMC_OWNER_TELEGRAM_ID):
        self.owner_telegram_id = int(owner_telegram_id)

    def is_owner(self, telegram_user_id: int) -> bool:
        return int(telegram_user_id) == self.owner_telegram_id

    @staticmethod
    def flow(telegram_user_id: int) -> OwnerFlow | None:
        return OwnerFlow.get_or_none(
            OwnerFlow.telegram_user_id == telegram_user_id
        )

    @staticmethod
    def set_flow(telegram_user_id: int, action: str, payload: dict | None = None):
        flow, _ = OwnerFlow.get_or_create(
            telegram_user_id=telegram_user_id,
            defaults={'action': action, 'payload': '{}'},
        )
        flow.action = action
        flow.payload = json.dumps(payload or {}, ensure_ascii=False)
        flow.created_at = dt.datetime.now()
        flow.save()
        return flow

    @staticmethod
    def clear_flow(telegram_user_id: int) -> None:
        OwnerFlow.delete().where(
            OwnerFlow.telegram_user_id == telegram_user_id
        ).execute()

    @staticmethod
    def active_teachers() -> list[TeacherIdentity]:
        return list(
            TeacherIdentity.select()
            .where(TeacherIdentity.active == True)  # noqa: E712
            .order_by(TeacherIdentity.django_username)
        )

    @staticmethod
    def create_invite(django_username: str, created_by: int) -> str:
        now = dt.datetime.now()
        TeacherInvite.update(used_at=now).where(
            (TeacherInvite.django_username == django_username)
            & (TeacherInvite.used_at.is_null(True))
        ).execute()
        token = secrets.token_urlsafe(24)
        TeacherInvite.create(
            token_hash=_token_hash(token),
            django_username=django_username,
            created_by_telegram_id=created_by,
            expires_at=now + INVITE_TTL,
        )
        return token

    @staticmethod
    def claim_invite(token: str, telegram_user_id: int) -> TeacherIdentity:
        now = dt.datetime.now()
        with db.atomic():
            invite = TeacherInvite.get_or_none(
                TeacherInvite.token_hash == _token_hash(token)
            )
            if invite is None or invite.used_at is not None:
                raise ValueError('Ссылка недействительна или уже использована.')
            if invite.expires_at < now:
                invite.used_at = now
                invite.save(only=(TeacherInvite.used_at,))
                raise ValueError('Срок действия ссылки истёк.')

            telegram_mapping = TeacherIdentity.get_or_none(
                TeacherIdentity.telegram_user_id == telegram_user_id
            )
            username_mapping = TeacherIdentity.get_or_none(
                TeacherIdentity.django_username == invite.django_username
            )
            if (
                telegram_mapping is not None
                and telegram_mapping.django_username != invite.django_username
            ):
                raise ValueError(
                    'Этот Telegram уже привязан к другому преподавателю.'
                )

            try:
                if username_mapping is not None:
                    username_mapping.telegram_user_id = telegram_user_id
                    username_mapping.active = True
                    username_mapping.save()
                    identity = username_mapping
                elif telegram_mapping is not None:
                    telegram_mapping.django_username = invite.django_username
                    telegram_mapping.active = True
                    telegram_mapping.save()
                    identity = telegram_mapping
                else:
                    identity = TeacherIdentity.create(
                        telegram_user_id=telegram_user_id,
                        django_username=invite.django_username,
                        active=True,
                    )
            except IntegrityError as exc:
                raise ValueError(
                    'Не удалось создать уникальную привязку преподавателя.'
                ) from exc

            invite.used_at = now
            invite.save(only=(TeacherInvite.used_at,))
            return identity


class TeacherManagementService:
    def __init__(
        self,
        bot: Any,
        client: Any,
        store: TeacherManagementStore | None = None,
    ):
        self.bot = bot
        self.client = client
        self.store = store or TeacherManagementStore()

    def is_owner(self, telegram_user_id: int) -> bool:
        return self.store.is_owner(telegram_user_id)

    def has_owner_flow(self, telegram_user_id: int) -> bool:
        return self.is_owner(telegram_user_id) and bool(
            self.store.flow(telegram_user_id)
        )

    def send_menu(self, chat_id: int, telegram_user_id: int) -> None:
        self._require_owner(telegram_user_id)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(types.InlineKeyboardButton(
            '➕ Добавить преподавателя',
            callback_data='tm:add',
        ))
        keyboard.row(types.InlineKeyboardButton(
            '📋 Telegram-привязки',
            callback_data='tm:list',
        ))
        self.bot.send_message(
            chat_id,
            'Управление преподавателями CourseMC',
            reply_markup=keyboard,
        )

    def begin_add_teacher(self, chat_id: int, telegram_user_id: int) -> None:
        self._require_owner(telegram_user_id)
        self.store.set_flow(telegram_user_id, ADD_TEACHER_ACTION)
        self.bot.send_message(
            chat_id,
            'Отправьте логин существующего преподавателя CourseMC. '
            'Я проверю его и создам одноразовую ссылку '
            'для привязки Telegram. Для отмены отправьте /cancel.',
        )

    def handle_owner_input(self, message: Any) -> None:
        telegram_user_id = message.from_user.id
        self._require_owner(telegram_user_id)
        flow = self.store.flow(telegram_user_id)
        if flow is None:
            return
        text = (message.text or '').strip()
        if text == '/cancel':
            self.store.clear_flow(telegram_user_id)
            self.bot.send_message(message.chat.id, 'Действие отменено.')
            return
        if flow.action != ADD_TEACHER_ACTION:
            self.store.clear_flow(telegram_user_id)
            self.bot.send_message(message.chat.id, 'Сценарий устарел. Начните заново.')
            return
        if not text or any(character.isspace() for character in text):
            self.bot.send_message(message.chat.id, 'Нужен один логин без пробелов.')
            return

        self.client.get_solutions(0, text, limit=1)
        username = text
        token = self.store.create_invite(username, telegram_user_id)
        self.store.clear_flow(telegram_user_id)
        bot_username = os.getenv('TELEGRAM_BOT_USERNAME', '').strip().lstrip('@')
        if not bot_username:
            bot_username = self.bot.get_me().username
        invite_url = f'https://t.me/{bot_username}?start=teacher_{token}'
        self.bot.send_message(
            message.chat.id,
            f'Преподаватель найден: {username}.\n\n'
            'Перешлите ему эту одноразовую ссылку (действует 48 часов):\n'
            f'{invite_url}\n\n'
            'После перехода его Telegram будет привязан к этому логину. '
            'Работы будут определяться закреплением учеников на сайте.',
        )

    def claim_start_payload(self, message: Any) -> bool:
        parts = (message.text or '').split(maxsplit=1)
        if len(parts) != 2 or not parts[1].startswith('teacher_'):
            return False
        token = parts[1][len('teacher_'):]
        try:
            identity = self.store.claim_invite(token, message.from_user.id)
        except ValueError as exc:
            self.bot.send_message(message.chat.id, str(exc))
        else:
            self.bot.send_message(
                message.chat.id,
                'Telegram успешно привязан к преподавателю '
                f'{identity.django_username}. Теперь сюда будут приходить '
                'работы закреплённых за вами учеников.',
            )
        return True

    def send_overview(self, chat_id: int, telegram_user_id: int) -> None:
        self._require_owner(telegram_user_id)
        teachers = self.store.active_teachers()
        lines = ['Telegram-привязки преподавателей:']
        for teacher in teachers:
            lines.append(
                f'\n• {teacher.django_username} — Telegram ID '
                f'{teacher.telegram_user_id}'
            )
        if not teachers:
            lines.append('\nПока нет подключённых преподавателей.')
        self.bot.send_message(chat_id, ''.join(lines))

    def _require_owner(self, telegram_user_id: int) -> None:
        if not self.is_owner(telegram_user_id):
            raise PermissionError('Управление доступно только владельцу курса.')


class TeacherManagementHandlers:
    def __init__(self, bot: Any, service_provider: Callable[[], TeacherManagementService]):
        self.bot = bot
        self.service_provider = service_provider

    def pending_filter(self, message: Any) -> bool:
        try:
            return self.service_provider().has_owner_flow(message.from_user.id)
        except RuntimeError:
            return False

    def open_menu(self, message: Any) -> None:
        try:
            self.service_provider().send_menu(message.chat.id, message.from_user.id)
        except PermissionError:
            self.bot.send_message(message.chat.id, 'Управление доступно только владельцу курса.')

    def handle_owner_input(self, message: Any) -> None:
        try:
            self.service_provider().handle_owner_input(message)
        except CourseMCAPIError as exc:
            text = (
                'Пользователь с таким логином не найден на CourseMC.'
                if exc.status_code == 404
                else 'CourseMC временно не принял запрос. Попробуйте ещё раз.'
            )
            self.bot.send_message(message.chat.id, text)
        except requests.RequestException:
            self.bot.send_message(message.chat.id, 'Сайт временно недоступен. Попробуйте ещё раз.')

    def handle_start_payload(self, message: Any) -> bool:
        return self.service_provider().claim_start_payload(message)

    def handle_callback(self, call: Any) -> None:
        parts = (call.data or '').split(':')
        try:
            service = self.service_provider()
            if len(parts) == 2 and parts[1] == 'add':
                service.begin_add_teacher(call.message.chat.id, call.from_user.id)
            elif len(parts) == 2 and parts[1] == 'list':
                service.send_overview(call.message.chat.id, call.from_user.id)
            else:
                raise ValueError('Кнопка устарела.')
            result = 'Готово.'
        except PermissionError:
            result = 'Управление доступно только владельцу курса.'
        except ValueError as exc:
            result = str(exc)
        except CourseMCAPIError as exc:
            result = (
                'Объект больше не найден на CourseMC.'
                if exc.status_code == 404
                else 'CourseMC временно не принял запрос.'
            )
        except requests.RequestException:
            result = 'Сайт временно недоступен.'
        self.bot.answer_callback_query(call.id, result, show_alert=False)


_service: TeacherManagementService | None = None


def get_teacher_management_service(bot: Any | None = None) -> TeacherManagementService:
    global _service
    if _service is None:
        if bot is None:
            from config import bot as configured_bot

            bot = configured_bot
        _service = TeacherManagementService(bot, client_from_environment())
    return _service


def register_teacher_management_handlers(bot: Any) -> TeacherManagementHandlers:
    handlers = TeacherManagementHandlers(
        bot,
        lambda: get_teacher_management_service(bot),
    )
    bot.message_handler(commands=['teachers'])(handlers.open_menu)
    bot.message_handler(
        func=lambda message: message.text == 'Преподаватели 👨‍🏫',
    )(handlers.open_menu)
    bot.message_handler(
        func=handlers.pending_filter,
        content_types=['text'],
    )(handlers.handle_owner_input)
    bot.callback_query_handler(
        func=lambda call: (call.data or '').startswith('tm:'),
    )(handlers.handle_callback)
    return handlers
