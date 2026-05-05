from telethon import TelegramClient
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji, UpdateMessageReactions
from telethon.utils import get_peer_id

from src.core.config import AppConfig
from src.core.logging import get_logger
from src.db.repository import MappingRepository

log = get_logger(__name__)


async def handle_reaction(
    update: UpdateMessageReactions,
    client: TelegramClient,
    repo: MappingRepository,
    cfg: AppConfig,
) -> None:
    src_chat_id = get_peer_id(update.peer)

    if not cfg.is_monitored(src_chat_id):
        return

    mapping = await repo.get_mirror(src_chat_id, update.msg_id)
    if mapping is None:
        return

    if mapping.src_chat_id == src_chat_id:
        mirror_chat_id, mirror_msg_id = mapping.dst_chat_id, mapping.dst_msg_id
    else:
        mirror_chat_id, mirror_msg_id = mapping.src_chat_id, mapping.src_msg_id

    # Pick the most popular standard emoji reaction; skip Premium custom emoji
    top_reaction: ReactionEmoji | None = None
    top_count = 0
    if update.reactions and update.reactions.results:
        for rc in update.reactions.results:
            if isinstance(rc.reaction, ReactionEmoji) and rc.count > top_count:
                top_count = rc.count
                top_reaction = rc.reaction

    reaction_list = [top_reaction] if top_reaction is not None else []

    await client(SendReactionRequest(
        peer=mirror_chat_id,
        msg_id=mirror_msg_id,
        reaction=reaction_list,
    ))

    log.info(
        "reaction.mirrored",
        src_chat=src_chat_id,
        src_msg=update.msg_id,
        dst_chat=mirror_chat_id,
        dst_msg=mirror_msg_id,
        emoji=top_reaction.emoticon if top_reaction else None,
    )
