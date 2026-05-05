"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE message_mappings (
            id          BIGSERIAL PRIMARY KEY,
            src_chat_id BIGINT      NOT NULL,
            src_msg_id  INT         NOT NULL,
            dst_chat_id BIGINT      NOT NULL,
            dst_msg_id  INT         NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_src ON message_mappings(src_chat_id, src_msg_id)"
    )
    op.execute(
        "CREATE INDEX idx_dst ON message_mappings(dst_chat_id, dst_msg_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS message_mappings")
