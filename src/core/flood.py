import asyncio
from collections.abc import Callable, Coroutine
from typing import TypeVar

from telethon.errors import FloodWaitError

from src.core.logging import get_logger

T = TypeVar("T")
log = get_logger(__name__)


async def with_flood_wait(fn: Callable[[], Coroutine[None, None, T]]) -> T:
    """Call fn(); on FloodWaitError sleep the required time and retry once."""
    try:
        return await fn()
    except FloodWaitError as e:
        log.warning("flood_wait", seconds=e.seconds)
        await asyncio.sleep(e.seconds + 1)
        return await fn()
