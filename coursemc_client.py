"""HTTP client for the protected CourseMC bot API."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CourseMCAPIError(Exception):
    """A non-retriable or exhausted CourseMC API response."""

    def __init__(self, status_code: int | None, message: str):
        super().__init__(message)
        self.status_code = status_code


class FileTooLargeError(CourseMCAPIError):
    """A solution attachment exceeds the configured Telegram limit."""


class CourseMCClient:
    """Small, retrying client that never puts the token in URLs or logs."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: tuple[float, float] = (5.0, 20.0),
        download_timeout: tuple[float, float] = (5.0, 30.0),
        max_file_size: int = 50 * 1024 * 1024,
        session: requests.Session | None = None,
    ) -> None:
        if not token:
            raise RuntimeError('Не задан COURSEMC_BOT_API_TOKEN')
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.download_timeout = download_timeout
        self.max_file_size = max_file_size
        self.session = session or self._build_session()
        self.session.headers.update({'X-CourseMC-Bot-Token': token})

    @staticmethod
    def _build_session() -> requests.Session:
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            status=2,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset({'GET', 'PATCH'}),
            raise_on_status=False,
        )
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        return session

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise CourseMCAPIError(
                response.status_code,
                f'CourseMC API вернул HTTP {response.status_code}',
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise CourseMCAPIError(
                response.status_code,
                'CourseMC API вернул некорректный JSON',
            ) from exc
        if not isinstance(payload, dict):
            raise CourseMCAPIError(
                response.status_code,
                'CourseMC API вернул неожиданный формат ответа',
            )
        return payload

    def get_solutions(
        self,
        cursor: int,
        teacher_username: str,
        *,
        limit: int = 50,
    ) -> dict[str, Any]:
        response = self.session.get(
            f'{self.base_url}/bot/lesson-solutions/',
            params={
                'after': cursor,
                'limit': limit,
                'teacher_username': teacher_username,
            },
            timeout=self.timeout,
        )
        return self._json(response)

    def review_solution(
        self,
        solution_id: int,
        reviewer_username: str,
        status: str,
        teacher_comment: str = '',
    ) -> dict[str, Any]:
        response = self.session.patch(
            f'{self.base_url}/bot/lesson-solutions/{solution_id}/review/',
            json={
                'reviewer_username': reviewer_username,
                'status': status,
                'teacher_comment': teacher_comment,
            },
            timeout=self.timeout,
        )
        return self._json(response)

    def download_file(self, file_info: dict[str, Any]) -> io.BytesIO:
        declared_size = int(file_info.get('size') or 0)
        if declared_size > self.max_file_size:
            raise FileTooLargeError(None, 'Файл превышает лимит Telegram')

        download_url = file_info['download_url']
        self._validate_download_url(download_url)
        response = self.session.get(
            download_url,
            timeout=self.download_timeout,
            stream=True,
        )
        if response.status_code >= 400:
            response.close()
            raise CourseMCAPIError(
                response.status_code,
                f'CourseMC API вернул HTTP {response.status_code}',
            )

        content_length = int(response.headers.get('Content-Length') or 0)
        if content_length > self.max_file_size:
            response.close()
            raise FileTooLargeError(None, 'Файл превышает лимит Telegram')

        result = io.BytesIO()
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                if result.tell() + len(chunk) > self.max_file_size:
                    raise FileTooLargeError(
                        None,
                        'Файл превышает лимит Telegram',
                    )
                result.write(chunk)
        finally:
            response.close()
        result.seek(0)
        result.name = self._safe_filename(file_info.get('original_name'))
        return result

    @staticmethod
    def _safe_filename(filename: str | None) -> str:
        name = Path(filename or 'solution-file').name
        return name.replace('\x00', '') or 'solution-file'

    def _validate_download_url(self, download_url: str) -> None:
        base = urlsplit(self.base_url)
        candidate = urlsplit(download_url)
        if (
            candidate.scheme not in {'http', 'https'}
            or candidate.scheme != base.scheme
            or candidate.netloc != base.netloc
        ):
            raise CourseMCAPIError(
                None,
                'CourseMC API вернул недопустимый адрес файла',
            )


def client_from_environment() -> CourseMCClient:
    return CourseMCClient(
        os.getenv('COURSEMC_API_BASE_URL', 'https://coursemc.ru/api/v1'),
        os.getenv('COURSEMC_BOT_API_TOKEN', ''),
        max_file_size=int(
            os.getenv('COURSEMC_TELEGRAM_MAX_FILE_SIZE', str(50 * 1024 * 1024))
        ),
    )
