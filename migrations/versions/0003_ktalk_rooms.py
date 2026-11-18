"""Stable room keys and join links for Kontur.Talk."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("meeting", sa.Column(
        "ktalk_room_key", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")
    ))
    op.create_unique_constraint("uq_meeting_ktalk_room_key", "meeting", ["ktalk_room_key"])
    op.add_column("meeting", sa.Column("ktalk_url", sa.String(255)))


def downgrade():
    op.drop_column("meeting", "ktalk_url")
    op.drop_column("meeting", "ktalk_room_key")
