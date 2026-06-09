from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session, selectinload

from app.models.db import CharacterRecord, ConversationTurnRecord, ResearchContextRecord, SceneRecord
from app.models.db import CharacterSessionRecord
from app.models.schemas import Character, ChatResponse, Scene


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
