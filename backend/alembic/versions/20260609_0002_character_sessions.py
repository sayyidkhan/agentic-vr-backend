"""add character sessions

Revision ID: 20260609_0002
Revises: 20260609_0001
Create Date: 2026-06-09 00:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260609_0002"
down_revision = "20260609_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(), nullable=False),
        sa.Column("character_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.character_id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(op.f("ix_character_sessions_scene_id"), "character_sessions", ["scene_id"], unique=False)
    op.create_index(op.f("ix_character_sessions_character_id"), "character_sessions", ["character_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_character_sessions_character_id"), table_name="character_sessions")
    op.drop_index(op.f("ix_character_sessions_scene_id"), table_name="character_sessions")
    op.drop_table("character_sessions")
