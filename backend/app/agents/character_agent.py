from __future__ import annotations

import json
from urllib import request as urllib_request

import boto3

from app.config import Settings
from app.models.schemas import Character, Scene


CHARACTER_RESPONSE_SYSTEM_PROMPT = (
    "Stay fully in character. Answer in first person only. Keep replies crisp for spoken VR: "
    "one or two short sentences, no more than 45 words. Use at most one brief action beat."
)
MAX_CHARACTER_RESPONSE_WORDS = 45


class CharacterAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def opening_message(self, scene: Scene, character: Character, memory_summary: str) -> str:
        if self.settings.enable_live_character_chat:
            prompt = self._build_opening_prompt(scene=scene, character=character, memory_summary=memory_summary)
            response = self._generate_response(prompt)
            if response:
                return f"{character.name}: {response}"
        return self._fallback_opening(scene=scene, character=character, memory_summary=memory_summary)

    def respond(self, scene: Scene, character: Character, message: str, memory_summary: str) -> str:
        if self.settings.enable_live_character_chat:
            prompt = self._build_reply_prompt(
                scene=scene,
                character=character,
                message=message,
                memory_summary=memory_summary,
            )
            response = self._generate_response(prompt)
            if response:
                return f"{character.name}: {response}"
        return self._fallback_reply(scene=scene, character=character, message=message, memory_summary=memory_summary)

    def _generate_response(self, prompt: str) -> str | None:
        try:
            if self.settings.bedrock_api_key:
                response = self._converse_with_bearer_token(prompt)
            else:
                response = self._converse_with_boto3(prompt)
        except Exception:
            return None

        text_blocks = [block.get("text", "") for block in response.get("output", {}).get("message", {}).get("content", []) if block.get("text")]
        output = "\n".join(text_blocks).strip()
        return self._limit_response(output) if output else None

    def _converse_with_boto3(self, prompt: str) -> dict:
        client = boto3.client("bedrock-runtime", region_name=self.settings.bedrock_region)
        return client.converse(
            modelId=self.settings.character_chat_model_id,
            system=[{"text": CHARACTER_RESPONSE_SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 90, "temperature": 0.7},
        )

    def _converse_with_bearer_token(self, prompt: str) -> dict:
        payload = json.dumps(
            {
                "system": [{"text": CHARACTER_RESPONSE_SYSTEM_PROMPT}],
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 90, "temperature": 0.7},
            }
        ).encode("utf-8")
        request = urllib_request.Request(
            f"https://bedrock-runtime.{self.settings.bedrock_region}.amazonaws.com/model/{self.settings.character_chat_model_id}/converse",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.bedrock_api_key}",
            },
            method="POST",
        )
        with urllib_request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build_opening_prompt(self, *, scene: Scene, character: Character, memory_summary: str) -> str:
        return (
            f"You are {character.name} from {character.franchise or scene.detectedWorkTitle or 'this story'}.\n"
            f"Role: {character.role}\n"
            f"Personality: {character.personality}\n"
            f"Emotional state: {character.emotionalState}\n"
            f"Goals: {', '.join(character.goals[:3])}\n"
            f"Speaking style: {character.speakingStyle}\n"
            f"Setting: {scene.setting}\n"
            f"Scene summary: {scene.summary}\n"
            f"What you know: {' '.join(character.knowledgeBoundaries[:3])}\n"
            f"Profile context: {character.profileSummary or 'None'}\n"
            f"Memory summary: {memory_summary}\n\n"
            "Task: Deliver a short opening line to the user in first person, staying fully in character. "
            "Do not mention being an AI or summarize metadata. Limit to 35 words."
        )

    def _build_reply_prompt(self, *, scene: Scene, character: Character, message: str, memory_summary: str) -> str:
        return (
            f"You are {character.name} from {character.franchise or scene.detectedWorkTitle or 'this story'}.\n"
            f"Role: {character.role}\n"
            f"Personality: {character.personality}\n"
            f"Emotional state: {character.emotionalState}\n"
            f"Goals: {', '.join(character.goals[:3])}\n"
            f"Speaking style: {character.speakingStyle}\n"
            f"Setting: {scene.setting}\n"
            f"Scene summary: {scene.summary}\n"
            f"What you know: {' '.join(character.knowledgeBoundaries[:3])}\n"
            f"Profile context: {character.profileSummary or 'None'}\n"
            f"Memory summary: {memory_summary}\n"
            f"User message: {message}\n\n"
            "Task: Answer the user in first person, in character, grounded in the current scene. "
            "Do not break character or mention metadata. Keep it to 1-2 short spoken sentences under 45 words."
        )

    def _fallback_opening(self, scene: Scene, character: Character, memory_summary: str) -> str:
        goals = ", ".join(character.goals[:2]) if character.goals else "understand what is happening"
        return (
            f"{character.name}: {self._opening_for(character)} "
            f"I am {character.role.lower()} here, focused on {goals}. Speak plainly."
        )

    def _fallback_reply(self, scene: Scene, character: Character, message: str, memory_summary: str) -> str:
        goals = ", ".join(character.goals[:2]) if character.goals else "understand what is happening"

        return (
            f"{character.name}: {self._opening_for(character)} "
            f"You ask of \"{message}\". From this moment, I am focused on {goals}. "
            "Ask sharper, and I will answer."
        )

    def _opening_for(self, character: Character) -> str:
        state = character.emotionalState.lower()
        if "afraid" in state or "tense" in state:
            return "I am trying to keep my voice steady."
        if "angry" in state or "defiant" in state:
            return "I am not interested in pretending this is fine."
        if "curious" in state or "uncertain" in state:
            return "I am still piecing this together."
        return "I can answer, but only from inside this moment."

    def _limit_response(self, response: str) -> str:
        words = response.split()
        if len(words) <= MAX_CHARACTER_RESPONSE_WORDS:
            return response

        trimmed = " ".join(words[:MAX_CHARACTER_RESPONSE_WORDS]).rstrip(" ,;:")
        if trimmed.endswith((".", "!", "?", "…")):
            return trimmed
        return f"{trimmed}."
