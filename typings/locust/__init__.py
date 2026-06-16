"""Minimal Locust stub for optional load-test harness typing."""

from typing import Any, Callable


class User:
    """Locust user base class stub."""


def between(min_wait: float, max_wait: float) -> Callable[..., Any]:
    """Locust wait-time helper stub."""
    _ = (min_wait, max_wait)
    return lambda *_args, **_kwargs: None


def tag(*tags: str) -> Callable[..., Any]:
    """Locust task tag decorator stub."""
    _ = tags
    return lambda fn: fn


def task(*args: Any, **kwargs: Any) -> Callable[..., Any]:
    """Locust task decorator stub."""
    _ = (args, kwargs)
    return lambda fn: fn


class events:
    """Locust event hooks stub."""

    @staticmethod
    def init(listener: Callable[..., Any]) -> None:
        _ = listener
