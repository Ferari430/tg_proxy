from dataclasses import dataclass

import asyncpg


@dataclass
class MessageMapping:
    src_chat_id: int
    src_msg_id: int
    dst_chat_id: int
    dst_msg_id: int


class MappingRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(
        self,
        src_chat_id: int,
        src_msg_id: int,
        dst_chat_id: int,
        dst_msg_id: int,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO message_mappings
                    (src_chat_id, src_msg_id, dst_chat_id, dst_msg_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (src_chat_id, src_msg_id) DO NOTHING
                """,
                src_chat_id,
                src_msg_id,
                dst_chat_id,
                dst_msg_id,
            )

    async def get_by_src(
        self, src_chat_id: int, src_msg_id: int
    ) -> MessageMapping | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT src_chat_id, src_msg_id, dst_chat_id, dst_msg_id"
                " FROM message_mappings WHERE src_chat_id=$1 AND src_msg_id=$2",
                src_chat_id,
                src_msg_id,
            )
        if row is None:
            return None
        return MessageMapping(**dict(row))

    async def get_by_dst(
        self, dst_chat_id: int, dst_msg_id: int
    ) -> MessageMapping | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT src_chat_id, src_msg_id, dst_chat_id, dst_msg_id"
                " FROM message_mappings WHERE dst_chat_id=$1 AND dst_msg_id=$2",
                dst_chat_id,
                dst_msg_id,
            )
        if row is None:
            return None
        return MessageMapping(**dict(row))

    async def get_mirror(
        self, chat_id: int, msg_id: int
    ) -> MessageMapping | None:
        """Find mapping regardless of direction."""
        return await self.get_by_src(chat_id, msg_id) or await self.get_by_dst(
            chat_id, msg_id
        )

    async def delete_mapping(self, chat_id: int, msg_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM message_mappings
                WHERE (src_chat_id = $1 AND src_msg_id = $2)
                   OR (dst_chat_id = $1 AND dst_msg_id = $2)
                """,
                chat_id,
                msg_id,
            )
