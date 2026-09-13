"""Batch reaction/attachment endpoints hide private-channel ids."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from routers.features.workshop_chat.dependencies import (
    BATCH_MESSAGE_ID_CAP,
    filter_accessible_message_ids,
    parse_batch_message_ids,
)
from tests.typing_helpers import as_user


def test_parse_batch_message_ids_caps_length() -> None:
    """Unbounded comma lists must be truncated."""
    raw = ",".join(str(i) for i in range(BATCH_MESSAGE_ID_CAP + 25))
    parsed = parse_batch_message_ids(raw)
    assert len(parsed) == BATCH_MESSAGE_ID_CAP
    assert parsed[0] == 0
    assert parsed[-1] == BATCH_MESSAGE_ID_CAP - 1


@pytest.mark.asyncio
async def test_reactions_batch_hides_private_non_member() -> None:
    """A same-org non-member must not see another private channel's metadata."""

    async def _access(_db, message_id: int, _user) -> None:
        if message_id == 99:
            raise HTTPException(status_code=403, detail="This channel is private")

    with patch(
        "routers.features.workshop_chat.dependencies.access_channel_message",
        new=AsyncMock(side_effect=_access),
    ):
        visible = await filter_accessible_message_ids(
            AsyncMock(),
            as_user(object()),
            [10, 99, 11],
        )
    assert visible == [10, 11]
