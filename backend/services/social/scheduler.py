"""Background scheduler that executes due social publish jobs."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger

from .service import run_publish_attempt
from .store import SocialStore, get_social_store


class SocialPublishScheduler:
    def __init__(self, *, store: SocialStore | None = None):
        self.store = store or get_social_store()
        self.poll_seconds = int(os.getenv("SOCIAL_SCHEDULER_POLL_SECONDS", "10"))
        self.max_concurrency = max(1, int(os.getenv("SOCIAL_SCHEDULER_CONCURRENCY", "3")))
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._run_loop(), name="social-publish-scheduler")
        logger.info("📣 Social publish scheduler started (poll={}s, concurrency={})", self.poll_seconds, self.max_concurrency)

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("📣 Social publish scheduler stopped")

    async def tick(self) -> None:
        jobs = self.store.list_due_jobs(limit=self.max_concurrency * 3)
        if not jobs:
            return

        async def _run(job: dict[str, Any]) -> None:
            async with self._semaphore:
                await asyncio.to_thread(run_publish_attempt, job, store=self.store)

        await asyncio.gather(*[_run(job) for job in jobs], return_exceptions=True)

    async def _run_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.tick()
            except Exception as exc:  # pragma: no cover - defensive loop guard
                logger.error("Social scheduler tick failed: {}", exc)
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                continue


_scheduler_instance: SocialPublishScheduler | None = None


def get_social_scheduler() -> SocialPublishScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SocialPublishScheduler()
    return _scheduler_instance
