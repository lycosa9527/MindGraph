"""Background Pipecat PipelineTask for Kitty JSON WebSocket ingress.

Today the pipeline is a single :class:`KittyWsMessageDispatchProcessor` that defers
to :func:`~services.kitty_voice.kitty_ws_inbound.dispatch_kitty_ws_inbound_message`
(so behavior matches the non-Pipecat receive loop). A separate
:class:`~services.kitty_voice.pipecat_kitty.processors.KittyOmniBridgeProcessor`
exists for future split of audio into dedicated frames without changing Omni or
hub contracts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pipecat.frames.frames import EndFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask

from services.kitty_voice.kitty_ws_inbound import KittyWsInboundContext
from services.kitty_voice.pipecat_kitty.frames import KittyWsMessageFrame
from services.kitty_voice.pipecat_kitty.processors import KittyWsMessageDispatchProcessor

logger = logging.getLogger(__name__)


class KittyPipecatWsPipeline:
    """Owns a :class:`PipelineTask` that processes :class:`KittyWsMessageFrame` instances."""

    def __init__(self, ctx: KittyWsInboundContext) -> None:
        self._ctx = ctx
        self._task: Optional[PipelineTask] = None
        self._runner_task: Optional[asyncio.Task] = None
        self._started = asyncio.Event()

    async def _cleanup_failed_start(self) -> None:
        """Cancel a runner that never reached ``on_pipeline_started`` (best-effort)."""
        if self._runner_task is not None and not self._runner_task.done():
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
        self._runner_task = None
        self._task = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._started = asyncio.Event()
        processor = KittyWsMessageDispatchProcessor(self._ctx, name="KittyWsDispatch")
        inner = Pipeline([processor])
        params = PipelineParams(
            audio_in_sample_rate=24000,
            audio_out_sample_rate=24000,
            enable_heartbeats=False,
            enable_metrics=False,
            enable_usage_metrics=False,
        )
        self._task = PipelineTask(
            inner,
            params=params,
            enable_rtvi=False,
            enable_turn_tracking=False,
            idle_timeout_secs=None,
            check_dangling_tasks=False,
        )

        @self._task.event_handler("on_pipeline_started")
        async def _on_started(_t, _f):
            self._started.set()

        runner = PipelineRunner(handle_sigint=False, handle_sigterm=False)

        async def _run() -> None:
            try:
                await runner.run(self._task)
            finally:
                logger.debug("Kitty Pipecat runner finished")

        self._runner_task = asyncio.create_task(_run())
        try:
            await asyncio.wait_for(self._started.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            logger.error("Kitty Pipecat pipeline did not start within 15s; aborting runner")
            await self._cleanup_failed_start()
            raise

    async def enqueue_client_message(self, message: dict) -> None:
        if self._task is None:
            raise RuntimeError("KittyPipecatWsPipeline not started")
        await self._task.queue_frame(KittyWsMessageFrame(message=message))

    async def stop(self) -> None:
        if self._task is None:
            return
        try:
            await self._task.queue_frame(EndFrame())
        except (asyncio.CancelledError, RuntimeError) as err:
            logger.debug("Kitty Pipecat stop: %s", err)
        if self._runner_task is not None:
            await asyncio.wait([self._runner_task], timeout=30.0)
        self._task = None
        self._runner_task = None
