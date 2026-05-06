from telethon import TelegramClient, events

from src.core.config import AppConfig
from src.core.flood import with_flood_wait
from src.core.logging import get_logger
from src.db.repository import MappingRepository

log = get_logger(__name__)


async def handle_delete(
    event: events.MessageDeleted.Event,
    client: TelegramClient,
    repo: MappingRepository,
    cfg: AppConfig,
) -> None:
    src_chat_id: int | None = event.chat_id
    if src_chat_id is None:
        return

    if not cfg.is_monitored(src_chat_id):
        return

    for deleted_id in event.deleted_ids:
        mapping = await repo.get_mirror(src_chat_id, deleted_id)
        if mapping is None:
            continue

        if mapping.src_chat_id == src_chat_id:
            mirror_chat_id = mapping.dst_chat_id
            mirror_msg_id = mapping.dst_msg_id
        else:
            mirror_chat_id = mapping.src_chat_id
            mirror_msg_id = mapping.src_msg_id

        try:
            chat, msg = mirror_chat_id, mirror_msg_id

            async def _do_delete(c: int = chat, m: int = msg) -> None:
                await client.delete_messages(c, [m])

            await with_flood_wait(_do_delete)
        except Exception:
            log.exception(
                "delete.mirror_failed",
                src_chat=src_chat_id,
                src_msg=deleted_id,
            )
            continue

        await repo.delete_mapping(src_chat_id, deleted_id)

        log.info(
            "message.deleted",
            src_chat=src_chat_id,
            src_msg=deleted_id,
            dst_chat=mirror_chat_id,
            dst_msg=mirror_msg_id,
        )
