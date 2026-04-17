"""DingTalk Stream SDK manager — background WebSocket for AI card callbackType=STREAM.

The Stream SDK WebSocket connection is required by DingTalk before it will accept
``createAndDeliver`` with ``callbackType: "STREAM"`` for group AI cards.  Streaming
content is still pushed via REST ``PUT /v1.0/card/streaming`` — the WebSocket is only
needed as a registration/validation channel; it also receives card interaction callbacks
(button clicks etc.) which we ACK without further action.

Operations
----------
- Expect **one** Stream SDK client per distinct DingTalk app ``client_id`` in a process.
  Multiple orgs sharing the same app reuse the same client.
- Clients are cleared only on process shutdown (``stop_all``). After **mass credential
  churn** or rotating many distinct apps in one long-lived worker, **restart uvicorn
  workers** so stale entries are dropped (rare in production).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from utils.env_helpers import env_int

logger = logging.getLogger(__name__)


def _import_sdk() -> Any:
    """Return the dingtalk_stream module, raising ImportError with a helpful message."""
    try:
        import dingtalk_stream  # pylint: disable=import-outside-toplevel

        return dingtalk_stream
    except ImportError as exc:
        raise ImportError(
            "dingtalk-stream is required for group AI card streaming. Run: pip install dingtalk-stream>=0.24.3"
        ) from exc


def _make_card_callback_handler_class(sdk: Any) -> type:
    """
    Dynamically build a ``CallbackHandler`` subclass after the SDK is imported.

    The SDK's ``DingTalkStreamClient`` calls ``handler.pre_start()`` during
    startup.  We must inherit from ``sdk.CallbackHandler`` so that method exists;
    a plain class without it causes an ``AttributeError`` on every connection
    attempt which triggers the reconnect loop immediately.
    """

    class _CardCallbackHandler(sdk.CallbackHandler):
        """
        Minimal ACK handler for card interaction callbacks.

        Card streaming content is pushed via REST independently; this handler
        only acknowledges interactive events (button clicks, form submissions)
        so DingTalk does not retry them.
        """

        async def process(self, callback: Any) -> tuple[int, str]:
            data = callback.data if hasattr(callback, "data") else {}
            out_track = (data or {}).get("outTrackId", "") if isinstance(data, dict) else ""
            logger.debug(
                "[MindBot] dingtalk_card_callback_ack outTrackId=%s",
                out_track,
            )
            return sdk.AckMessage.STATUS_OK, "OK"

    return _CardCallbackHandler


class DingTalkStreamManager:
    """
    Singleton that owns one ``DingTalkStreamClient`` per unique ``client_id``.

    Clients are started lazily on the first ``ensure_client`` call and kept alive
    via a reconnect loop.  ``stop_all`` cancels all tasks on application shutdown.
    """

    _instance: Optional["DingTalkStreamManager"] = None

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> "DingTalkStreamManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def ensure_client(self, client_id: str, client_secret: str) -> None:
        """
        Lazy-start a Stream SDK client for ``client_id`` if one is not already running.

        Waits 1.5 s after spawning the background task so the WebSocket handshake
        can complete before the caller proceeds with ``createAndDeliver``.
        Subsequent calls for the same ``client_id`` return immediately.
        """
        if not client_id or not client_secret:
            logger.warning(
                "[MindBot] ensure_client_skipped reason=empty_credentials"
                " (group AI card callbackType=STREAM will be rejected by DingTalk)"
            )
            return
        async with self._lock:
            existing_task = self._tasks.get(client_id)
            if client_id in self._clients and existing_task is not None and not existing_task.done():
                return
            max_clients = env_int("MINDBOT_STREAM_CLIENT_MAX_KEYS", 50)
            if len(self._clients) >= max_clients:
                logger.error(
                    "[MindBot] dingtalk_stream_client_cap_reached count=%s max=%s "
                    "client_id=%s — refusing to add new Stream SDK client; "
                    "restart workers or raise MINDBOT_STREAM_CLIENT_MAX_KEYS",
                    len(self._clients),
                    max_clients,
                    client_id,
                )
                return
            sdk = _import_sdk()
            from dingtalk_stream import Card_Callback_Router_Topic  # pylint: disable=import-outside-toplevel

            credential = sdk.Credential(client_id, client_secret)
            client = sdk.DingTalkStreamClient(credential)
            handler_cls = _make_card_callback_handler_class(sdk)
            client.register_callback_handler(Card_Callback_Router_Topic, handler_cls())
            self._clients[client_id] = client
            task = asyncio.create_task(
                self._run(client_id, client),
                name=f"dingtalk_stream_{client_id[:12]}",
            )
            self._tasks[client_id] = task
            logger.info(
                "[MindBot] dingtalk_stream_client_started client_id=%s",
                client_id,
            )
        await asyncio.sleep(1.5)

    async def _run(self, client_id: str, client: Any) -> None:
        """
        Reconnect loop with exponential back-off and a consecutive-error circuit stop.

        ``client.start()`` is a long-running coroutine that blocks until the
        WebSocket disconnects.  On any exception we wait with exponential back-off
        (starting at 5 s, capped at ``MINDBOT_STREAM_CLIENT_MAX_BACKOFF_S``, default
        300 s) and retry.  After ``MINDBOT_STREAM_CLIENT_MAX_ERRORS`` (default 20)
        consecutive errors without a successful connection the loop exits with an
        ERROR log — ops must restart the worker to resume streaming.

        A clean disconnect (no exception from ``client.start()``) resets the
        consecutive-error counter so brief network blips do not exhaust the budget.
        """
        _backoff_base = 5.0
        max_backoff = float(max(5, env_int("MINDBOT_STREAM_CLIENT_MAX_BACKOFF_S", 300)))
        max_errors = max(1, env_int("MINDBOT_STREAM_CLIENT_MAX_ERRORS", 20))
        consecutive_errors = 0
        backoff = _backoff_base

        try:
            while True:
                try:
                    await client.start()
                    logger.info(
                        "[MindBot] dingtalk_stream_client_disconnected client_id=%s reconnecting",
                        client_id,
                    )
                    consecutive_errors = 0
                    backoff = _backoff_base
                except asyncio.CancelledError:
                    logger.info(
                        "[MindBot] dingtalk_stream_client_cancelled client_id=%s",
                        client_id,
                    )
                    return
                except Exception as exc:  # pylint: disable=broad-except
                    consecutive_errors += 1
                    logger.warning(
                        "[MindBot] dingtalk_stream_client_error client_id=%s "
                        "consecutive_errors=%s/%s err=%s backoff_s=%.1f",
                        client_id,
                        consecutive_errors,
                        max_errors,
                        exc,
                        backoff,
                    )
                    if consecutive_errors >= max_errors:
                        logger.critical(
                            "[MindBot] dingtalk_stream_client_giving_up client_id=%s "
                            "consecutive_errors=%s — entering long-backoff recovery; "
                            "group AI card streaming will be unavailable until reconnected",
                            client_id,
                            consecutive_errors,
                        )
                        # Long-backoff self-healing: wait, then exit the loop so the
                        # finally block clears the entry from _clients/_tasks.
                        # ensure_client will recreate the client on the next card request.
                        recovery_backoff = float(max(60, env_int("MINDBOT_STREAM_CLIENT_RECOVERY_BACKOFF_S", 300)))
                        await asyncio.sleep(recovery_backoff)
                        logger.warning(
                            "[MindBot] dingtalk_stream_client_recovery_attempt client_id=%s "
                            "clearing_entry_for_reconnect",
                            client_id,
                        )
                        return
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
        finally:
            async with self._lock:
                self._clients.pop(client_id, None)
                self._tasks.pop(client_id, None)
                logger.info(
                    "[MindBot] dingtalk_stream_client_cleaned_up client_id=%s "
                    "(will be recreated on next ensure_client call)",
                    client_id,
                )

    def is_client_running(self, client_id: str) -> bool:
        """Return True if a Stream SDK task is registered for ``client_id``."""
        task = self._tasks.get(client_id)
        return task is not None and not task.done()

    def registered_client_count(self) -> int:
        """Number of DingTalk Stream SDK clients held in this process (one per ``client_id``)."""
        return len(self._clients)

    async def stop_all(self) -> None:
        """
        Cancel all SDK client tasks and wait for them to finish.

        Awaiting the cancelled tasks ensures they handle ``CancelledError`` cleanly
        and avoids ``Task was destroyed but it is pending!`` warnings during
        interpreter shutdown.  Safe to call from the FastAPI lifespan ``finally``
        block.
        """
        pending = []
        for client_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                pending.append(task)
                logger.info(
                    "[MindBot] dingtalk_stream_client_stopped client_id=%s",
                    client_id,
                )
        self._tasks.clear()
        self._clients.clear()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


def get_stream_manager() -> DingTalkStreamManager:
    """Return the process-wide ``DingTalkStreamManager`` singleton."""
    return DingTalkStreamManager.get()
