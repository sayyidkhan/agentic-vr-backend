from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session, selectinload

from app.models.db import CharacterRecord, CharacterSessionRecord, ConversationTurnRecord, ResearchContextRecord, SceneRecord, VideoRecord
from app.models.schemas import Character, ChatResponse, Scene, VideoAsset


class SQLiteStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_scene(self, scene: Scene) -> None:
        record = SceneRecord(
            scene_id=scene.sceneId,
            video_id=scene.videoId,
            timestamp=scene.timestamp,
            frame_ref=scene.frameRef,
            transcript_segment=scene.transcriptSegment,
            summary=scene.summary,
            setting=scene.setting,
            emotional_tone=scene.emotionalTone,
            conflict=scene.conflict,
            objects_json=json.dumps(scene.objects),
            director_context=scene.directorContext,
            memory_summary=scene.memorySummary,
        )
        record.characters = [
            CharacterRecord(
                character_id=character.characterId,
                scene_id=scene.sceneId,
                name=character.name,
                role=character.role,
                personality=character.personality,
                emotional_state=character.emotionalState,
                goals_json=json.dumps(character.goals),
                knowledge_boundaries_json=json.dumps(character.knowledgeBoundaries),
                speaking_style=character.speakingStyle,
            )
            for character in scene.characters
        ]

        self.db.merge(record)
        self.db.commit()

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        record = (
            self.db.query(SceneRecord)
            .options(selectinload(SceneRecord.characters))
            .filter(SceneRecord.scene_id == scene_id)
            .one_or_none()
        )
        if record is None:
            return None

        return Scene(
            sceneId=record.scene_id,
            videoId=record.video_id,
            timestamp=record.timestamp,
            frameRef=record.frame_ref,
            transcriptSegment=record.transcript_segment,
            summary=record.summary,
            setting=record.setting,
            emotionalTone=record.emotional_tone,
            conflict=record.conflict,
            objects=json.loads(record.objects_json),
            characters=[
                Character(
                    characterId=character.character_id,
                    sceneId=character.scene_id,
                    name=character.name,
                    role=character.role,
                    personality=character.personality,
                    emotionalState=character.emotional_state,
                    goals=json.loads(character.goals_json),
                    knowledgeBoundaries=json.loads(character.knowledge_boundaries_json),
                    speakingStyle=character.speaking_style,
                )
                for character in record.characters
            ],
            directorContext=record.director_context,
            memorySummary=record.memory_summary,
            createdAt=record.created_at,
        )

    def update_memory_summary(self, scene_id: str, memory_summary: str) -> None:
        record = self.db.get(SceneRecord, scene_id)
        if record is None:
            return
        record.memory_summary = memory_summary
        self.db.commit()

    def save_turn(self, scene_id: str, user_message: str, response: ChatResponse) -> None:
        self.db.add(
            ConversationTurnRecord(
                turn_id=f"turn_{uuid4().hex[:12]}",
                scene_id=scene_id,
                user_message=user_message,
                selected_agent=response.respondingAgent.name,
                agent_type=response.respondingAgent.type,
                agent_response=response.response,
                memory_summary_after_turn=response.updatedMemorySummary,
                agent_trace_json=json.dumps([step.model_dump() for step in response.agentTrace]),
            )
        )
        self.db.commit()

    def save_research(self, scene_id: str, query: str, summary: str) -> None:
        self.db.add(
            ResearchContextRecord(
                research_id=f"research_{uuid4().hex[:12]}",
                scene_id=scene_id,
                query=query,
                summary=summary,
                used_by_agent="director",
            )
        )
        self.db.commit()

    def create_character_session(self, scene_id: str, character_id: str) -> str:
        session_id = f"character_session_{uuid4().hex[:12]}"
        self.db.add(
            CharacterSessionRecord(
                session_id=session_id,
                scene_id=scene_id,
                character_id=character_id,
            )
        )
        self.db.commit()
        return session_id

    def create_video_link(self, url: str, source_type: str, title: str | None = None) -> VideoAsset:
        record = VideoRecord(
            video_id=f"video_{uuid4().hex[:12]}",
            source_type=source_type,
            title=title,
            original_url=url,
            status="ready",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._video_asset_from_record(record)

    def create_uploaded_video(
        self,
        *,
        video_id: str,
        title: str | None,
        original_filename: str | None,
        storage_backend: str,
        storage_key: str,
        playback_url: str,
        content_type: str | None,
        file_size_bytes: int | None,
    ) -> VideoAsset:
        record = VideoRecord(
            video_id=video_id,
            source_type="upload",
            title=title,
            original_filename=original_filename,
            storage_backend=storage_backend,
            storage_key=storage_key,
            playback_url=playback_url,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            status="ready",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._video_asset_from_record(record)

    def list_videos(self, *, limit: int, offset: int) -> tuple[list[VideoAsset], int]:
        query = self.db.query(VideoRecord)
        total = query.count()
        records = query.order_by(VideoRecord.created_at.desc()).offset(offset).limit(limit).all()
        return [self._video_asset_from_record(record) for record in records], total

    def get_video(self, video_id: str) -> VideoAsset | None:
        record = self.db.get(VideoRecord, video_id)
        if record is None:
            return None
        return self._video_asset_from_record(record)

    def update_video(self, video_id: str, changes: dict[str, object]) -> VideoAsset | None:
        record = self.db.get(VideoRecord, video_id)
        if record is None:
            return None

        if "title" in changes:
            record.title = self._empty_string_to_none(changes["title"])
        if "sourceType" in changes and changes["sourceType"] is not None:
            record.source_type = str(changes["sourceType"])
        if "originalUrl" in changes:
            record.original_url = self._empty_string_to_none(changes["originalUrl"])
        if "playbackUrl" in changes:
            record.playback_url = self._empty_string_to_none(changes["playbackUrl"])
        if "status" in changes and changes["status"] is not None:
            record.status = str(changes["status"]).strip() or "ready"

        self.db.commit()
        self.db.refresh(record)
        return self._video_asset_from_record(record)

    def delete_video(self, video_id: str) -> bool:
        record = self.db.get(VideoRecord, video_id)
        if record is None:
            return False

        self.db.delete(record)
        self.db.commit()
        return True

    @staticmethod
    def _empty_string_to_none(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _video_asset_from_record(record: VideoRecord) -> VideoAsset:
        return VideoAsset(
            videoId=record.video_id,
            sourceType=record.source_type,
            title=record.title,
            originalUrl=record.original_url,
            originalFilename=record.original_filename,
            storageBackend=record.storage_backend,
            storageKey=record.storage_key,
            playbackUrl=record.playback_url,
            contentType=record.content_type,
            fileSizeBytes=record.file_size_bytes,
            status=record.status,
            createdAt=record.created_at,
            updatedAt=record.updated_at,
        )
