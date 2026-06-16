"""Shared typing helpers for test modules."""

from __future__ import annotations

from typing import Any, TypeVar, cast

from models.domain.auth import Organization, User

_T = TypeVar("_T")


def as_organization(org: object) -> Organization:
    """Cast a test fake or namespace to Organization for typed call sites."""
    return cast(Organization, org)


def as_user(user: object) -> User:
    """Cast a test fake or namespace to User for typed call sites."""
    return cast(User, user)


def as_type(value: object, expected: type[_T]) -> _T:
    """Cast a test double to an expected type."""
    _ = expected
    return cast(_T, value)


def mock_await_args(mock: Any) -> tuple[Any, ...]:
    """Return await args from an AsyncMock after asserting a call occurred."""
    await_args = mock.await_args
    assert await_args is not None
    return await_args.args


def mock_await_kwargs(mock: Any) -> dict[str, Any]:
    """Return await kwargs from an AsyncMock after asserting a call occurred."""
    await_args = mock.await_args
    assert await_args is not None
    return await_args.kwargs


def mock_call_args(mock: Any) -> tuple[Any, ...]:
    """Return call args from a Mock after asserting a call occurred."""
    call = mock.call_args
    assert call is not None
    return call.args


def mock_call_kwargs(mock: Any) -> dict[str, Any]:
    """Return call kwargs from a Mock after asserting a call occurred."""
    call = mock.call_args
    assert call is not None
    return call.kwargs
