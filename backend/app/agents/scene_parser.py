import json
from pathlib import Path
from uuid import uuid4

from app.agents.memory_agent import MemoryAgent
from app.models.schemas import AgentTraceStep, AnalyzeSceneRequest, AnalyzeSceneResponse, Character, Scene


class SceneParserAgent:
    def __init__(self) -> None:
        self.memory_agent = MemoryAgent()
        self.fallback_path = Path(__file__).resolve().parents[1] / "data" / "fallback_scene.json"

    def analyze(self, payload: AnalyzeSceneRequest) -> AnalyzeSceneResponse:
        scene = self._fallback_scene(payload)
        scene.memorySummary = self.memory_agent.initial_summary(scene)

        return AnalyzeSceneResponse(
            sceneId=scene.sceneId,
            sceneSummary=scene.summary,
            scene=scene,
            characters=scene.characters,
            directorContext=scene.directorContext,
            memorySummary=scene.memorySummary,
            agentTrace=[
                AgentTraceStep(step="receive_frame", agent="api", status="complete"),
                AgentTraceStep(step="parse_scene", agent="scene_parser", status="fallback"),
                AgentTraceStep(step="initialize_memory", agent="memory", status="complete"),
            ],
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
        )
