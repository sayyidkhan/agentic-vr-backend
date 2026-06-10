from __future__ import annotations

import re

from app.models.schemas import AgentTraceStep, Character, CharacterRouterResponse, RespondingAgent, Scene


class CharacterRouterAgent:
    def route(self, scene: Scene, message: str, target_agent_id: str | None = None) -> CharacterRouterResponse:
        trace = [
            AgentTraceStep(step="receive_character_request", agent="character_router", status="complete"),
            AgentTraceStep(step="score_scene_characters", agent="character_router", status="complete"),
        ]
        character, reason, confidence = self._select_character(scene, message, target_agent_id)
        trace.append(
            AgentTraceStep(
                step="select_character_agent",
                agent="character_router",
                status="complete",
                detail=f"{character.name} selected with confidence {confidence:.2f}",
            )
        )

        return CharacterRouterResponse(
            sceneId=scene.sceneId,
            targetAgent=RespondingAgent(id=character.characterId, name=character.name, type="character"),
            reason=reason,
            confidence=confidence,
            agentTrace=trace,
        )

    def _select_character(
        self,
        scene: Scene,
        message: str,
        target_agent_id: str | None,
    ) -> tuple[Character, str, float]:
        if not scene.characters:
            raise ValueError("No characters are available for routing")

        explicit_target = self._find_by_id(scene.characters, target_agent_id)
        if explicit_target is not None:
            return explicit_target, f"Explicit target agent id matched {explicit_target.name}.", 0.98

        normalized_message = self._normalize(message)
        scored = [(character, self._score_character(character, normalized_message)) for character in scene.characters]
        scored.sort(key=lambda item: item[1], reverse=True)
        selected, score = scored[0]

        if score >= 5:
            return selected, f"User mentioned {selected.name} directly.", 0.92
        if score >= 2:
            return selected, f"Request matched {selected.name}'s role, goals, or personality.", 0.72

        return selected, f"No explicit character was named, so the scene lead {selected.name} was selected.", 0.45

    @staticmethod
    def _find_by_id(characters: list[Character], target_agent_id: str | None) -> Character | None:
        if not target_agent_id:
            return None
        return next((character for character in characters if character.characterId == target_agent_id), None)

    def _score_character(self, character: Character, normalized_message: str) -> int:
        score = 0
        if self._contains_phrase(normalized_message, character.name):
            score += 5

        for phrase in [character.role, character.personality, character.emotionalState, character.speakingStyle]:
            score += self._phrase_score(normalized_message, phrase)

        for phrase in [*character.goals, *character.knowledgeBoundaries]:
            score += self._phrase_score(normalized_message, phrase)

        return score

    @staticmethod
    def _phrase_score(normalized_message: str, phrase: str | None) -> int:
        if not phrase:
            return 0
        tokens = [token for token in re.split(r"[^a-z0-9]+", phrase.lower()) if len(token) >= 4]
        matches = sum(1 for token in set(tokens) if token in normalized_message)
        return min(matches, 3)

    def _contains_phrase(self, normalized_message: str, phrase: str | None) -> bool:
        if not phrase:
            return False
        normalized_phrase = self._normalize(phrase)
        return bool(normalized_phrase and re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized_message))

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.lower().strip())
