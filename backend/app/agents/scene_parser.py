from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.agents.memory_agent import MemoryAgent
from app.config import Settings
from app.models.schemas import AgentTraceStep, AnalyzeSceneRequest, AnalyzeSceneResponse, Character, Scene
from app.services.exa_service import ExaService
from app.services.scene_analysis import SceneAnalysisService


class SceneParserAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory_agent = MemoryAgent()
        self.fallback_path = Path(__file__).resolve().parents[1] / "data" / "fallback_scene.json"
        self.scene_analysis_service = SceneAnalysisService(settings=settings)
        self.exa_service = ExaService(settings=settings)

    def analyze(self, payload: AnalyzeSceneRequest) -> AnalyzeSceneResponse:
        agent_trace = [AgentTraceStep(step="receive_frame", agent="api", status="complete")]
        analysis_mode = "fallback"
        source_model_id = None

        if self.settings.enable_live_scene_analysis and payload.frame:
            try:
                live_analysis = self.scene_analysis_service.analyze(
                    frame_data_url=payload.frame,
                    transcript_segment=payload.transcriptSegment,
                    video_title=payload.videoMetadata.title if payload.videoMetadata else None,
                )
                scene = self._live_scene(payload=payload, analysis_payload=live_analysis.payload)
                source_model_id = live_analysis.model_id
                analysis_mode = "live"
                agent_trace.append(
                    AgentTraceStep(
                        step="parse_scene",
                        agent="scene_parser",
                        status="complete",
                        detail=f"Parsed with model {live_analysis.model_id}",
                    )
                )
                enriched_count = self._enrich_characters(scene)
                agent_trace.append(
                    AgentTraceStep(
                        step="enrich_characters",
                        agent="research",
                        status="complete" if enriched_count > 0 else "fallback",
                        detail=f"Exa enrichment applied to {enriched_count} character(s)" if enriched_count > 0 else "No Exa enrichment applied",
                    )
                )
            except Exception as exc:
                scene = self._fallback_scene(payload)
                agent_trace.append(
                    AgentTraceStep(
                        step="parse_scene",
                        agent="scene_parser",
                        status="fallback",
                        detail=f"Live analysis failed: {type(exc).__name__}",
                    )
                )
        else:
            scene = self._fallback_scene(payload)
            agent_trace.append(AgentTraceStep(step="parse_scene", agent="scene_parser", status="fallback"))

        scene.memorySummary = self.memory_agent.initial_summary(scene)
        agent_trace.append(AgentTraceStep(step="initialize_memory", agent="memory", status="complete"))

        return AnalyzeSceneResponse(
            sceneId=scene.sceneId,
            sceneSummary=scene.summary,
            scene=scene,
            characters=scene.characters,
            directorContext=scene.directorContext,
            memorySummary=scene.memorySummary,
            agentTrace=agent_trace,
            analysisMode=analysis_mode,
            sourceModelId=source_model_id,
        )

    def _fallback_scene(self, payload: AnalyzeSceneRequest) -> Scene:
        fallback = json.loads(self.fallback_path.read_text())
        scene_id = f"scene_{uuid4().hex[:12]}"
        video_id = payload.videoMetadata.videoId if payload.videoMetadata and payload.videoMetadata.videoId else "demo-video"
        transcript = payload.transcriptSegment or fallback.get("transcriptSegment")

        characters = [
            Character(
                characterId=f"{scene_id}_{item['slug']}",
                sceneId=scene_id,
                name=item["name"],
                role=item["role"],
                personality=item["personality"],
                emotionalState=item["emotionalState"],
                goals=item["goals"],
                knowledgeBoundaries=item["knowledgeBoundaries"],
                speakingStyle=item["speakingStyle"],
            )
            for item in fallback["characters"]
        ]

        summary = fallback["summary"]
        if transcript:
            summary = f"{summary} Transcript context: {transcript}"

        return Scene(
            sceneId=scene_id,
            videoId=video_id,
            timestamp=payload.timestamp,
            frameRef="inline-frame" if payload.frame else None,
            transcriptSegment=transcript,
            summary=summary,
            setting=fallback["setting"],
            emotionalTone=fallback["emotionalTone"],
            conflict=fallback["conflict"],
            objects=fallback["objects"],
            characters=characters,
            directorContext=fallback["directorContext"],
            memorySummary="",
            createdAt=None,
            analysisMode="fallback",
        )

    def _live_scene(self, payload: AnalyzeSceneRequest, analysis_payload: dict) -> Scene:
        scene_id = f"scene_{uuid4().hex[:12]}"
        video_id = payload.videoMetadata.videoId if payload.videoMetadata and payload.videoMetadata.videoId else "demo-video"
        characters = []
        for index, item in enumerate(analysis_payload.get("characters", [])[: self.settings.scene_analysis_max_characters]):
            name = self._clean_string(item.get("name")) or f"Character {index + 1}"
            characters.append(
                Character(
                    characterId=f"{scene_id}_{self._slugify(name)}",
                    sceneId=scene_id,
                    name=name,
                    role=self._clean_string(item.get("role")) or "Unclear role in the scene",
                    personality=self._clean_string(item.get("personality")) or "Unclear personality from this frame",
                    emotionalState=self._clean_string(item.get("emotionalState")) or "emotionally unclear",
                    goals=self._clean_string_list(item.get("goals")) or ["Understand what is happening in the scene"],
                    knowledgeBoundaries=self._clean_string_list(item.get("knowledgeBoundaries")) or ["Only knows what can be inferred from this moment in the scene."],
                    speakingStyle=self._clean_string(item.get("speakingStyle")) or "speaks cautiously based on the moment",
                    franchise=self._clean_string(item.get("franchise")) or self._clean_string(analysis_payload.get("detectedUniverse")),
                    portrayedBy=self._clean_string(item.get("portrayedBy")),
                    identificationConfidence=self._clean_confidence(item.get("confidence")),
                )
            )

        if not characters:
            raise ValueError("No characters were returned from live analysis")

        return Scene(
            sceneId=scene_id,
            videoId=video_id,
            timestamp=payload.timestamp,
            frameRef="inline-frame" if payload.frame else None,
            transcriptSegment=payload.transcriptSegment,
            summary=self._clean_string(analysis_payload.get("sceneSummary")) or "Scene analysis returned no summary.",
            setting=self._clean_string(analysis_payload.get("setting")) or "Unknown setting",
            emotionalTone=self._clean_string(analysis_payload.get("emotionalTone")) or "unclear tone",
            conflict=self._clean_string(analysis_payload.get("conflict")) or "central conflict unclear",
            objects=self._clean_string_list(analysis_payload.get("objects")) or [],
            characters=characters,
            directorContext=self._clean_string(analysis_payload.get("directorContext")) or "No director context returned.",
            memorySummary="",
            createdAt=None,
            detectedWorkTitle=self._clean_string(analysis_payload.get("detectedWorkTitle")),
            detectedUniverse=self._clean_string(analysis_payload.get("detectedUniverse")),
            analysisMode="live",
        )

    def _enrich_characters(self, scene: Scene) -> int:
        enriched = 0
        for character in scene.characters:
            if not character.name or character.name.lower().startswith("unknown"):
                continue
            profile = self.exa_service.build_character_profile(
                character_name=character.name,
                work_title=scene.detectedWorkTitle,
                franchise=character.franchise or scene.detectedUniverse,
            )
            if profile is None:
                continue
            character.profileSummary = profile.summary
            character.profileSources = profile.sources
            if profile.summary:
                knowledge_note = f"Public profile context: {profile.summary[:220]}"
                if knowledge_note not in character.knowledgeBoundaries:
                    character.knowledgeBoundaries.append(knowledge_note)
            enriched += 1
        return enriched

    def _clean_string(self, value: object) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return None

    def _clean_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    cleaned.append(text)
        return cleaned

    def _clean_confidence(self, value: object) -> float | None:
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        return None

    def _slugify(self, value: str) -> str:
        cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value)
        compact = "_".join(part for part in cleaned.split("_") if part)
        return compact[:48] or uuid4().hex[:8]
