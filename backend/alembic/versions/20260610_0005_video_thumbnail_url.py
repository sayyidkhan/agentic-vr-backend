"""add video thumbnail url

Revision ID: 20260610_0005
Revises: 20260609_0004
Create Date: 2026-06-10 14:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260610_0005"
down_revision = "20260609_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("thumbnail_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "thumbnail_url")
