from __future__ import annotations

from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class SceneRecord(Base):
    __tablename__ = "scenes"

    scene_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    video_id: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    frame_ref: Mapped[Optional[str]] = mapped_column(Text)
    transcript_segment: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    setting: Mapped[str] = mapped_column(Text, nullable=False)
    emotional_tone: Mapped[str] = mapped_column(Text, nullable=False)
    conflict: Mapped[str] = mapped_column(Text, nullable=False)
    objects_json: Mapped[str] = mapped_column(Text, nullable=False)
    director_context: Mapped[str] = mapped_column(Text, nullable=False)
    memory_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    characters: Mapped[List["CharacterRecord"]] = relationship(
        back_populates="scene",
        cascade="all, delete-orphan",
    )


class CharacterRecord(Base):
    __tablename__ = "characters"

    character_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.scene_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    personality: Mapped[str] = mapped_column(Text, nullable=False)
    emotional_state: Mapped[str] = mapped_column(Text, nullable=False)
    goals_json: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_boundaries_json: Mapped[str] = mapped_column(Text, nullable=False)
    speaking_style: Mapped[str] = mapped_column(Text, nullable=False)

    scene: Mapped[SceneRecord] = relationship(back_populates="characters")


class ConversationTurnRecord(Base):
    __tablename__ = "conversation_turns"

    turn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.scene_id"), nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    selected_agent: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    agent_response: Mapped[str] = mapped_column(Text, nullable=False)
    memory_summary_after_turn: Mapped[str] = mapped_column(Text, nullable=False)
    agent_trace_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ResearchContextRecord(Base):
    __tablename__ = "research_contexts"

    research_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.scene_id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    used_by_agent: Mapped[str] = mapped_column(String(120), nullable=False, default="director")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CharacterSessionRecord(Base):
    __tablename__ = "character_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.scene_id"), nullable=False, index=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.character_id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class VideoRecord(Base):
    __tablename__ = "videos"

    video_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    original_url: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    storage_backend: Mapped[str | None] = mapped_column(String(32))
    storage_key: Mapped[str | None] = mapped_column(Text)
    playback_url: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(120))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
