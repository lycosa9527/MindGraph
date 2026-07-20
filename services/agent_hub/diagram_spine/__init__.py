"""Diagram command spine — Bus front door for agent diagram mutations.

Do not eagerly import ``bus`` here: package init runs when importing
``diagram_spine.origins`` (e.g. from ``services.agent_hub``), and ``bus`` pulls
``diagram_edit.executor``, which can re-enter this package mid-import.
"""

from services.agent_hub.diagram_spine.origins import (
    DiagramCommandOrigin,
    register_channel_adapter,
)
from services.agent_hub.diagram_spine.types import DiagramCommandRequest, DiagramCommandResult

__all__ = [
    "DiagramCommandOrigin",
    "DiagramCommandRequest",
    "DiagramCommandResult",
    "register_channel_adapter",
]
