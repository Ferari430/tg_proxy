import asyncio
import random

from telethon import TelegramClient, events
from telethon.tl.types import Message

from src.core.config import AppConfig
from src.core.flood import with_flood_wait
from src.core.logging import get_logger
from src.db.repository import MappingRepository

log = get_logger(__name__)


async def handle_album(
    event: events.Album.Event,
    client: TelegramClient,
    repo: MappingRepository,
    cfg: AppConfig,
) -> None:
    msgs: list[Message] = event.messages
    if not msgs:
        return

    # Skip albums sent by the userbot itself (outgoing)
    if msgs[0].out:
        return

    first = msgs[0]
    src_chat_id: int = event.chat_id

    target_chat_id = cfg.find_mirror(src_chat_id)
    if target_chat_id is None:
        return

    # Dedup: check the first message — if it's in DB, the album was already forwarded
    if await repo.get_mirror(src_chat_id, first.id) is not None:
        return

    # Resolve reply from first message (Telegram puts reply context on first)
    reply_to: int | None = None
    if first.reply_to is not None and first.reply_to.reply_to_msg_id is not None:
        mapping = await repo.get_mirror(src_chat_id, first.reply_to.reply_to_msg_id)
        if mapping is not None:
            reply_to = (
                mapping.dst_msg_id
                if mapping.src_chat_id == src_chat_id
                else mapping.src_msg_id
            )

    delay = random.uniform(cfg.human_delay.min_seconds, cfg.human_delay.max_seconds)
    await asyncio.sleep(delay)

    files = [m.media for m in msgs]
    sent = await with_flood_wait(lambda: client.send_file(
        target_chat_id,
        file=files,
        caption=first.text or None,
        formatting_entities=first.entities if first.text else None,
        reply_to=reply_to,
    ))

    # send_file returns a list when multiple files are sent
    if not isinstance(sent, list):
        sent = [sent]

    for src_msg, dst_msg in zip(msgs, sent, strict=False):
        await repo.save(src_chat_id, src_msg.id, target_chat_id, dst_msg.id)

    log.info(
        "album.forwarded",
        src_chat=src_chat_id,
        dst_chat=target_chat_id,
        count=len(msgs),
    )
