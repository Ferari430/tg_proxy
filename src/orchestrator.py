import asyncio
from datetime import datetime

import pytz

from src.core.config import AppConfig
from src.core.logging import get_logger
from src.db.repository import MappingRepository
from src.worker import UserbotWorker

log = get_logger(__name__)

_SCHEDULE_CHECK_INTERVAL = 30  # seconds


class Orchestrator:
    """Manages worker lifecycle and account rotation by schedule."""

    def __init__(self, cfg: AppConfig, repo: MappingRepository) -> None:
        self._cfg = cfg
        self._repo = repo
        self._tz = pytz.timezone(cfg.timezone)
        self._workers: list[UserbotWorker] = []
        self._active_idx: int = 0

    async def run(self) -> None:
        for account in self._cfg.accounts:
            self._workers.append(
                UserbotWorker(
                    account=account,
                    cfg=self._cfg,
                    repo=self._repo,
                    api_id=self._cfg.telegram.api_id,
                    api_hash=self._cfg.telegram.api_hash,
                )
            )

        self._active_idx = self._get_active_index()
        await self._workers[self._active_idx].start(catch_up=False)
        log.info(
            "orchestrator.started",
            active=self._cfg.accounts[self._active_idx].session_file,
        )

        if len(self._workers) > 1:
            asyncio.create_task(self._schedule_loop())

        # Block forever (until cancelled)
        await asyncio.Event().wait()

    async def _schedule_loop(self) -> None:
        while True:
            await asyncio.sleep(_SCHEDULE_CHECK_INTERVAL)

            desired_idx = self._get_active_index()
            if desired_idx == self._active_idx:
                continue

            log.info(
                "orchestrator.switching",
                from_account=self._cfg.accounts[self._active_idx].session_file,
                to_account=self._cfg.accounts[desired_idx].session_file,
            )

            await self._workers[self._active_idx].stop()
            self._active_idx = desired_idx
            await self._workers[self._active_idx].start(catch_up=True)

            log.info(
                "orchestrator.switched",
                active=self._cfg.accounts[self._active_idx].session_file,
            )

    def _get_active_index(self) -> int:
        """Return index of the account that should be active right now."""
        if len(self._workers) == 1:
            return 0

        now = datetime.now(self._tz)
        current = now.hour * 60 + now.minute

        for i, account in enumerate(self._cfg.accounts):
            if account.active_hours is None:
                return i
            start = account.active_hours.start_minutes
            end = account.active_hours.end_minutes
            # Handle ranges that cross midnight (e.g. 20:00–08:00)
            if start < end:
                if start <= current < end:
                    return i
            else:
                if current >= start or current < end:
                    return i

        return 0  # fallback: first account
