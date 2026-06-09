"""add video descriptions

Revision ID: 20260609_0004
Revises: 20260609_0003
Create Date: 2026-06-10 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260609_0004"
down_revision = "20260609_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "description")
