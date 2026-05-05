import asyncio
import random

from telethon import TelegramClient, events
from telethon.tl.types import Message

from src.core.config import AppConfig
from src.core.logging import get_logger
from src.db.repository import MappingRepository

log = get_logger(__name__)


async def handle_new_message(
    event: events.NewMessage.Event,
    client: TelegramClient,
    repo: MappingRepository,
    cfg: AppConfig,
) -> None:
    msg: Message = event.message

    # Skip service messages (user joined, pinned, etc.)
    if msg.action is not None:
        return

    # Albums are handled separately (grouped_id collector)
    if msg.grouped_id is not None:
        return

    # Skip edge case: no text and no media (shouldn't happen after action check)
    if not msg.text and msg.media is None:
        return

    src_chat_id: int = event.chat_id
    target_chat_id = cfg.find_mirror(src_chat_id)
    if target_chat_id is None:
        return

    # Dedup: skip if already forwarded (covers catch_up replays and messages
    # sent by the other account that this client sees as incoming)
    if await repo.get_mirror(src_chat_id, msg.id) is not None:
        return

    # Resolve reply: find the mirror of the replied-to message
    reply_to: int | None = None
    if msg.reply_to is not None and msg.reply_to.reply_to_msg_id is not None:
        original_reply_id: int = msg.reply_to.reply_to_msg_id
        mapping = await repo.get_mirror(src_chat_id, original_reply_id)
        if mapping is not None:
            # Figure out which side is in the target chat
            reply_to = (
                mapping.dst_msg_id
                if mapping.src_chat_id == src_chat_id
                else mapping.src_msg_id
            )
        # If no mapping found → message predates the system, send without reply

    await _human_delay(cfg)

    if msg.media is not None:
        sent = await client.send_file(
            target_chat_id,
            file=msg.media,
            caption=msg.text,
            formatting_entities=msg.entities,
            reply_to=reply_to,
        )
    else:
        sent = await client.send_message(
            target_chat_id,
            msg.text,
            formatting_entities=msg.entities,
            reply_to=reply_to,
        )

    await repo.save(src_chat_id, msg.id, target_chat_id, sent.id)

    log.info(
        "message.forwarded",
        src_chat=src_chat_id,
        src_msg=msg.id,
        dst_chat=target_chat_id,
        dst_msg=sent.id,
        has_media=msg.media is not None,
    )


async def _human_delay(cfg: AppConfig) -> None:
    delay = random.uniform(cfg.human_delay.min_seconds, cfg.human_delay.max_seconds)
    await asyncio.sleep(delay)
