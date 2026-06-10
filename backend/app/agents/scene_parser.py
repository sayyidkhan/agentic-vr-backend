from __future__ import annotations

import json
import re
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
        if payload.videoMetadata and (
            payload.videoMetadata.title
            or payload.videoMetadata.description
            or payload.videoMetadata.agents
        ):
            return self._metadata_fallback_scene(payload)

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

    def _metadata_fallback_scene(self, payload: AnalyzeSceneRequest) -> Scene:
        scene_id = f"scene_{uuid4().hex[:12]}"
        metadata = payload.videoMetadata
        title = self._clean_string(metadata.title) if metadata else None
        description = self._clean_string(metadata.description) if metadata else None
        video_id = metadata.videoId if metadata and metadata.videoId else "catalogue-video"
        transcript = payload.transcriptSegment or description or title
        source_label = self._clean_string(metadata.sourceLabel) if metadata else None
        character_names = self._candidate_character_names(metadata)

        if not character_names:
            character_names = ["Scene Guide"]

        characters = [
            Character(
                characterId=f"{scene_id}_{self._slugify(name)}",
                sceneId=scene_id,
                name=name,
                role="Character inferred from catalogue metadata",
                personality="scene-aware, responsive, grounded in the referenced moment",
                emotionalState="focused on the paused scene",
                goals=[
                    "answer from inside the current scene context",
                    "help the viewer explore motivations, stakes, and visible details",
                ],
                knowledgeBoundaries=[
                    "Only knows the catalogue metadata, supplied transcript context, and visible scene cues.",
                    "Should avoid claiming precise plot facts that were not supplied.",
                ],
                speakingStyle="concise, cinematic, and grounded",
                franchise=title,
                identificationConfidence=0.45,
            )
            for name in character_names[: self.settings.scene_analysis_max_characters]
        ]

        source_note = f" from {source_label}" if source_label else ""
        summary_parts = [
            f"{title or 'This catalogue video'} is opened as an interactive SceneVerse moment{source_note}.",
            description or "",
            "The viewer can question the scene, ask characters about intent, or ask the Director for story-level context.",
        ]
        summary = " ".join(part for part in summary_parts if part).strip()

        return Scene(
            sceneId=scene_id,
            videoId=video_id,
            timestamp=payload.timestamp,
            frameRef="inline-frame" if payload.frame else None,
            transcriptSegment=transcript,
            summary=summary,
            setting=f"The referenced scene surface for {title or 'this catalogue video'}",
            emotionalTone="uncertain, exploratory, and cinematic",
            conflict="The viewer is trying to uncover character intent, scene stakes, and hidden tension from the available context",
            objects=["catalogue frame", "scene setting", "character focus", "source reference"],
            characters=characters,
            directorContext=(
                "Use the catalogue title, description, timestamp, and any supplied transcript as grounding. "
                "Be transparent when a detail is inferred rather than visually confirmed."
            ),
            memorySummary="",
            createdAt=None,
            detectedWorkTitle=title,
            detectedUniverse=title,
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
                    box=self._clean_box(item.get("box")),
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

    def _clean_box(self, value: object) -> list[float] | None:
        if not isinstance(value, list) or len(value) != 4:
            return None
        try:
            box = [min(1.0, max(0.0, float(coord))) for coord in value]
        except (TypeError, ValueError):
            return None
        left, top, right, bottom = box
        if right - left < 0.01 or bottom - top < 0.01:
            return None
        return [left, top, right, bottom]

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

    def _candidate_character_names(self, metadata) -> list[str]:
        if metadata is None:
            return []

        agent_candidates: list[str] = []
        for name in metadata.agents or []:
            cleaned = self._clean_string(name)
            if cleaned and self._looks_like_character_name(cleaned):
                agent_candidates.append(cleaned)

        if len(agent_candidates) >= 2:
            return self._unique_names(agent_candidates)[:4]

        candidates: list[str] = [*agent_candidates]

        text = " ".join(
            part
            for part in [self._clean_string(metadata.description), self._clean_string(metadata.title)]
            if part
        )
        for match in re.finditer(r"\b([A-Z][A-Za-z']{2,}(?:\s+[A-Z][A-Za-z']{2,}){0,2})\s*\(", text):
            candidate = self._clean_candidate_name(match.group(1))
            if candidate:
                candidates.append(candidate)

        normalized_text = re.sub(r"[^A-Za-z0-9' ]+", " ", text)
        for match in re.finditer(r"\b[A-Z][A-Za-z']{2,}\b", normalized_text):
            candidate = self._clean_candidate_name(match.group(0))
            if candidate:
                candidates.append(candidate)

        return self._unique_names(candidates)[:4]

    def _unique_names(self, candidates: list[str]) -> list[str]:
        unique: list[str] = []
        seen = set()
        for candidate in candidates:
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _clean_candidate_name(self, value: str) -> str | None:
        words = [word.strip("'") for word in value.split() if word.strip("'")]
        filtered = [word for word in words if self._looks_like_character_name(word)]
        if not filtered:
            return None
        if len(filtered) >= 2 and filtered[0].lower() in {"leonardo", "elliot"}:
            return None
        return " ".join(filtered[:2])

    def _looks_like_character_name(self, value: str) -> bool:
        lowered = value.strip().lower()
        if lowered in {
            "vera",
            "director",
            "scene",
            "agent",
            "scene agent",
            "youtube",
            "official",
            "video",
            "remaster",
            "the",
            "meeting",
            "dream",
            "ship",
            "duel",
            "flying",
            "official",
            "remaster",
            "movie",
            "title",
            "clip",
            "moment",
            "catalogue",
            "linked",
            "reference",
        }:
            return False
        return bool(re.match(r"^[A-Z][A-Za-z']+(?:\s+[A-Z][A-Za-z']+)?$", value.strip()))

    def _slugify(self, value: str) -> str:
        cleaned = "".join(character.lower() if character.isalnum() else "_" for character in value)
        compact = "_".join(part for part in cleaned.split("_") if part)
        return compact[:48] or uuid4().hex[:8]
