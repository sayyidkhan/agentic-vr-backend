"""add videos table

Revision ID: 20260609_0003
Revises: 20260609_0002
Create Date: 2026-06-09 21:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260609_0003"
down_revision = "20260609_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("video_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("storage_backend", sa.String(length=32), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("playback_url", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("video_id"),
    )
    op.create_index(op.f("ix_videos_source_type"), "videos", ["source_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_videos_source_type"), table_name="videos")
    op.drop_table("videos")
