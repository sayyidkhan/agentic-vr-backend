"""initial schema

Revision ID: 20260609_0001
Revises:
Create Date: 2026-06-09 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260609_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenes",
        sa.Column("scene_id", sa.String(length=64), nullable=False),
        sa.Column("video_id", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("frame_ref", sa.Text(), nullable=True),
        sa.Column("transcript_segment", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("setting", sa.Text(), nullable=False),
        sa.Column("emotional_tone", sa.Text(), nullable=False),
        sa.Column("conflict", sa.Text(), nullable=False),
        sa.Column("objects_json", sa.Text(), nullable=False),
        sa.Column("director_context", sa.Text(), nullable=False),
        sa.Column("memory_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scene_id"),
    )
    op.create_table(
        "characters",
        sa.Column("character_id", sa.String(length=96), nullable=False),
        sa.Column("scene_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("emotional_state", sa.Text(), nullable=False),
        sa.Column("goals_json", sa.Text(), nullable=False),
        sa.Column("knowledge_boundaries_json", sa.Text(), nullable=False),
        sa.Column("speaking_style", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"]),
        sa.PrimaryKeyConstraint("character_id"),
    )
    op.create_index(op.f("ix_characters_scene_id"), "characters", ["scene_id"], unique=False)
    op.create_table(
        "conversation_turns",
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("selected_agent", sa.String(length=120), nullable=False),
        sa.Column("agent_type", sa.String(length=40), nullable=False),
        sa.Column("agent_response", sa.Text(), nullable=False),
        sa.Column("memory_summary_after_turn", sa.Text(), nullable=False),
        sa.Column("agent_trace_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"]),
        sa.PrimaryKeyConstraint("turn_id"),
    )
    op.create_index(op.f("ix_conversation_turns_scene_id"), "conversation_turns", ["scene_id"], unique=False)
    op.create_table(
        "research_contexts",
        sa.Column("research_id", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("used_by_agent", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"]),
        sa.PrimaryKeyConstraint("research_id"),
    )
    op.create_index(op.f("ix_research_contexts_scene_id"), "research_contexts", ["scene_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_research_contexts_scene_id"), table_name="research_contexts")
    op.drop_table("research_contexts")
    op.drop_index(op.f("ix_conversation_turns_scene_id"), table_name="conversation_turns")
    op.drop_table("conversation_turns")
    op.drop_index(op.f("ix_characters_scene_id"), table_name="characters")
    op.drop_table("characters")
    op.drop_table("scenes")
