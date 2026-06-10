from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import Settings


class VoiceCharacter(BaseModel):
    character: str
    label: str
    provider: Literal["elevenlabs", "speechmatics"]
    voiceId: str
    predefinedText: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    enabled: bool = True


class VoiceRegistryFile(BaseModel):
    defaultSpeechmaticsVoiceId: str = "jack"
    characters: list[VoiceCharacter]


class VoiceRegistryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def registry(self) -> VoiceRegistryFile:
        registry_path = Path(self.settings.voice_registry_path)
        if not registry_path.is_absolute():
            registry_path = Path(__file__).resolve().parents[2] / registry_path

        body = json.loads(registry_path.read_text(encoding="utf-8"))
        return VoiceRegistryFile.model_validate(body)

    def resolve(self, name: str) -> VoiceCharacter | None:
        normalized = self._normalize_lookup_key(name)
        if not normalized:
            return None

        for entry in self.registry.characters:
            if not entry.enabled:
                continue
            keys = {entry.character, *entry.aliases}
            if normalized in {self._normalize_lookup_key(key) for key in keys}:
                return entry
        return None

    def list_preset_characters(self) -> list[VoiceCharacter]:
        return [
            entry
            for entry in self.registry.characters
            if entry.enabled and entry.predefinedText and entry.predefinedText.strip()
        ]

    def list_characters_for_provider(self, provider: Literal["elevenlabs", "speechmatics"]) -> list[VoiceCharacter]:
        return [entry for entry in self.registry.characters if entry.enabled and entry.provider == provider]

    def speechmatics_voice_id_for(self, name: str) -> str:
        entry = self.resolve(name)
        if entry and entry.provider == "speechmatics":
            voice_id = entry.voiceId.strip()
            if voice_id:
                return voice_id
        return self.registry.defaultSpeechmaticsVoiceId.strip()

    def predefined_text_for(self, name: str) -> str | None:
        entry = self.resolve(name)
        if entry is None:
            return None
        predefined_text = entry.predefinedText
        if predefined_text is None:
            return None
        stripped = predefined_text.strip()
        return stripped or None

    def provider_for(self, name: str) -> Literal["elevenlabs", "speechmatics"] | None:
        entry = self.resolve(name)
        if entry is None:
            return None
        return entry.provider

    @staticmethod
    def _normalize_lookup_key(name: str) -> str:
        return name.strip().lower()
