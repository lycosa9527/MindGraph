"""Celery stage lines for personal knowledge."""

import asyncio
import logging

from services.knowledge.personal_knowledge_log import (
    bind_personal_knowledge_task,
    log_personal_knowledge,
    reset_personal_knowledge_task,
)
from services.knowledge.vibeflow_store import document_prefix, toc_object_key


def test_stage_line_names_the_celery_task(caplog) -> None:
    """A worker stage line carries the status and the Celery task id."""
    token = bind_personal_knowledge_task("task-1")
    try:
        with caplog.at_level(logging.INFO):
            log_personal_knowledge("sending_oss", user=3, package=9, document=4, pieces=2)
    finally:
        reset_personal_knowledge_task(token)
    assert "status=sending_oss" in caplog.text
    assert "task=task-1" in caplog.text
    assert "user=3" in caplog.text
    assert "pieces=2" in caplog.text


def test_oss_failure_is_an_error(caplog) -> None:
    """An OSS failure is written at error level."""
    with caplog.at_level(logging.ERROR):
        log_personal_knowledge("oss_failed", user=3, package=9, document=4, reason="manifest")
    assert caplog.records
    assert caplog.records[-1].levelno == logging.ERROR
    assert "status=oss_failed" in caplog.records[-1].message


def test_task_id_reaches_the_async_worker_body(caplog) -> None:
    """The Celery task id stays visible inside asyncio.run, which is how the worker runs."""

    async def _body() -> None:
        log_personal_knowledge("splitting", user=3, package=9, document=4)

    token = bind_personal_knowledge_task("task-2")
    try:
        with caplog.at_level(logging.INFO):
            asyncio.run(_body())
    finally:
        reset_personal_knowledge_task(token)
    assert "status=splitting" in caplog.text
    assert "task=task-2" in caplog.text


def test_markdown_lands_inside_the_watched_prefix(monkeypatch) -> None:
    """Markdown is stored under the prefix VibeFlow watches. The manifest stays outside it."""
    monkeypatch.setenv("OSS_KEY_PREFIX", "dev_roy/backups")
    assert document_prefix(3, 9, 4) == "vibeflow/source/dev_roy/3/9/4"
    assert toc_object_key(3, 9, 4) == "dev_roy/knowledge/toc/3/9/4.json"
