"""Errors for the clip-teaching service."""

from __future__ import annotations


class ClipLessonError(Exception):
    """A rejected clip-teaching operation with an HTTP status."""

    def __init__(self, code: str, http_status: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status
