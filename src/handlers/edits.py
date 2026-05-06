from telethon import TelegramClient, events
from telethon.errors import MessageNotModifiedError
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import Message, ReactionEmoji

from src.core.config import AppConfig
from src.core.flood import with_flood_wait
from src.core.logging import get_logger
from src.db.repository import MappingRepository

log = get_logger(__name__)


async def handle_edit(
    event: events.MessageEdited.Event,
    client: TelegramClient,
    repo: MappingRepository,
    cfg: AppConfig,
) -> None:
    msg: Message = event.message
    src_chat_id: int = event.chat_id

    if not cfg.is_monitored(src_chat_id):
        return

    mapping = await repo.get_mirror(src_chat_id, msg.id)
    if mapping is None:
        return

    if mapping.src_chat_id == src_chat_id:
        mirror_chat_id, mirror_msg_id = mapping.dst_chat_id, mapping.dst_msg_id
    else:
        mirror_chat_id, mirror_msg_id = mapping.src_chat_id, mapping.src_msg_id

    try:
        await with_flood_wait(lambda: client.edit_message(
            mirror_chat_id, mirror_msg_id, msg.text, formatting_entities=msg.entities,
        ))
        log.info(
            "message.edited",
            src_chat=src_chat_id,
            src_msg=msg.id,
            dst_chat=mirror_chat_id,
            dst_msg=mirror_msg_id,
        )
    except MessageNotModifiedError:
        # In supergroups reactions on messages sent by others arrive as
        # UpdateEditChannelMessage. Mirror the current reaction state.
        top_reaction: ReactionEmoji | None = None
        top_count = 0
        if msg.reactions and msg.reactions.results:
            for rc in msg.reactions.results:
                if isinstance(rc.reaction, ReactionEmoji) and rc.count > top_count:
                    top_count = rc.count
                    top_reaction = rc.reaction

        await with_flood_wait(lambda: client(SendReactionRequest(
            peer=mirror_chat_id,
            msg_id=mirror_msg_id,
            reaction=[top_reaction] if top_reaction is not None else [],
        )))
