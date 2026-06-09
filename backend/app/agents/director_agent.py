from __future__ import annotations

from typing import Optional

from app.models.schemas import Scene


class DirectorAgent:
    def respond(self, scene: Scene, message: str, memory_summary: str, research_summary: Optional[str] = None) -> str:
        research_note = f" External context adds: {research_summary}" if research_summary else ""

        return (
            "Director Agent: This scene is built around "
            f"{scene.conflict.lower()}. The emotional register is {scene.emotionalTone.lower()}, "
            f"and the setting, {scene.setting}, compresses the characters into a high-pressure choice. "
            f"Your question was: \"{message}\". Based on the scene memory, {memory_summary}.{research_note}"
        )

    def validate_character_response(self, response: str) -> str:
        return response
