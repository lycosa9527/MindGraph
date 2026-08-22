"""Live handshake against Tencent realtime ASR V2.

Loads repo ``.env`` and opens ``wss://asr.cloud.tencent.com/asr/v2/<appid>``.
Requires ``TENCENT_ASR_APP_ID`` plus ``TENCENT_SMS_SECRET_*`` (or ASR-specific keys).

  python -m pytest tests/test_tencent_asr_v2_live.py -q -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.features.tencent_asr_v2 import TencentAsrV2Client, load_tencent_asr_credentials
from services.features.tencent_asr_v2_errors import TencentAsrClassifiedError
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv

_SILENCE_200MS = bytes(6400)


def _load_repo_dotenv() -> None:
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.mark.asyncio
async def test_tencent_asr_v2_live_handshake_and_end() -> None:
    """Sign, connect, handshake code=0, send PCM, finish with type=end."""
    _load_repo_dotenv()
    credentials = load_tencent_asr_credentials()
    assert credentials.app_id.isdigit()
    assert not credentials.app_id.startswith("140")

    errors: list[TencentAsrClassifiedError] = []

    async def on_snapshot(_sentences: object) -> None:
        return

    async def on_error(classified: TencentAsrClassifiedError) -> None:
        errors.append(classified)

    client = TencentAsrV2Client(
        on_snapshot=on_snapshot,
        on_error=on_error,
        speaker_diarization=False,
    )
    await client.start()
    assert client.voice_id
    await client.send_pcm(_SILENCE_200MS)
    await client.finish()
    assert not errors


@pytest.mark.asyncio
async def test_tencent_asr_v2_live_speaker_engine_handshake() -> None:
    """Speaker SKU handshake; falls back to 16k_zh_en_speaker if 2.0 is rejected."""
    _load_repo_dotenv()
    load_tencent_asr_credentials()

    errors: list[TencentAsrClassifiedError] = []

    async def on_snapshot(_sentences: object) -> None:
        return

    async def on_error(classified: TencentAsrClassifiedError) -> None:
        errors.append(classified)

    client = TencentAsrV2Client(
        on_snapshot=on_snapshot,
        on_error=on_error,
        speaker_diarization=True,
    )
    await client.start()
    await client.send_pcm(_SILENCE_200MS)
    await client.finish()
    assert not errors
