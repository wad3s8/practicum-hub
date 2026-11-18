"""Project curator selection and team meetings."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_curator",
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("project.id"), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("account.id"), primary_key=True),
    )
    op.create_index("ix_project_curator_account_id", "project_curator", ["account_id"])
    op.create_table(
        "meeting",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("team_id", sa.BigInteger(), sa.ForeignKey("team.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_meeting_team_start", "meeting", ["team_id", "starts_at", "id"])


def downgrade():
    op.drop_table("meeting")
    op.drop_table("project_curator")
