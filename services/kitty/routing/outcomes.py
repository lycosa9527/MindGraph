"""Typed-loop route outcome values (shared by the agent loop and tests)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RouteOutcome(str, Enum):
    """Terminal result of one Kitty text turn."""

    EXECUTED = "executed"
    CONVERSATIONAL_FALLBACK = "conversational_fallback"
    FAILED = "failed"


@dataclass(slots=True)
class RouteResult:
    """Outcome plus optional action name and reason."""

    outcome: RouteOutcome
    reason: Optional[str] = None
    action: Optional[str] = None
