from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings
from app.models.schemas import SpeechCharacterPreset
from app.services.voice_registry import VoiceRegistryService

try:
    import certifi
except ImportError:  # pragma: no cover - certifi is expected through requests/httpx dependencies.
    certifi = None


@dataclass(frozen=True)
class SpeechAudio:
    character: str
    provider: str
    voice_id: str
    model_id: str
    output_format: str
    text: str
    content: bytes

    @property
    def media_type(self) -> str:
        codec = self.output_format.split("_", 1)[0]
        if codec == "mp3":
            return "audio/mpeg"
        if codec == "wav":
            return "audio/wav"
        if codec == "pcm":
            return "audio/L16"
        if codec == "ulaw":
            return "audio/basic"
        return "application/octet-stream"

    @property
    def filename(self) -> str:
        extension = self.output_format.split("_", 1)[0] or "audio"
        return f"sceneverse-{self.character}.{extension}"


class ElevenLabsConfigurationError(Exception):
    pass


class ElevenLabsSpeechError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ElevenLabsSpeechService:
    base_url = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(self, settings: Settings, voice_registry: VoiceRegistryService) -> None:
        self.settings = settings
        self.voice_registry = voice_registry
        self._ssl_context = self._create_ssl_context()

    def list_character_presets(self) -> list[SpeechCharacterPreset]:
        return [
            SpeechCharacterPreset(
                character=entry.character,
                label=entry.label,
                predefinedText=entry.predefinedText or "",
                voiceIdConfigured=self._voice_id_for(entry.character) is not None,
            )
            for entry in self.voice_registry.list_characters_for_provider("elevenlabs")
            if entry.predefinedText
        ]

    def synthesize_predefined(self, character: str) -> SpeechAudio:
        normalized_character = self._normalize_character(character)
        predefined_text = self.voice_registry.predefined_text_for(normalized_character)
        if not predefined_text:
            raise ValueError(f"No predefined speech line configured for '{character}'")
        return self.synthesize(character=normalized_character, text=predefined_text)

    def synthesize(self, character: str, text: str) -> SpeechAudio:
        normalized_character = self._normalize_character(character)
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Speech text must not be empty")

        api_key = self.settings.elevenlabs_api_key
        if not api_key:
            raise ElevenLabsConfigurationError("ELEVENLABS_API_KEY is not configured")

        voice_id = self._voice_id_for(normalized_character)
        if not voice_id:
            raise ElevenLabsConfigurationError(
                f"No ElevenLabs voiceId configured for '{normalized_character}' in {self.settings.voice_registry_path}"
            )

        output_format = self.settings.elevenlabs_output_format
        query = urlencode({"output_format": output_format})
        request = Request(
            url=f"{self.base_url}/{voice_id}?{query}",
            data=json.dumps(
                {
                    "text": normalized_text,
                    "model_id": self.settings.elevenlabs_tts_model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
                "xi-api-key": api_key,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=30, context=self._ssl_context) as response:
                return SpeechAudio(
                    character=normalized_character,
                    provider="elevenlabs",
                    voice_id=voice_id,
                    model_id=self.settings.elevenlabs_tts_model_id,
                    output_format=output_format,
                    text=normalized_text,
                    content=response.read(),
                )
        except HTTPError as exc:
            status_code = 503 if exc.code in {401, 403} else 502
            raise ElevenLabsSpeechError(self._read_error(exc), status_code=status_code) from exc
        except URLError as exc:
            raise ElevenLabsSpeechError(f"ElevenLabs request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ElevenLabsSpeechError("ElevenLabs request timed out") from exc

    def _voice_id_for(self, character: str) -> str | None:
        entry = self.voice_registry.resolve(character)
        if entry is None or entry.provider != "elevenlabs":
            return None
        voice_id = entry.voiceId.strip()
        return voice_id or None

    def _normalize_character(self, character: str) -> str:
        entry = self.voice_registry.resolve(character)
        if entry is None or entry.provider != "elevenlabs":
            supported = ", ".join(
                sorted(entry.character for entry in self.voice_registry.list_characters_for_provider("elevenlabs"))
            )
            raise ValueError(f"Unsupported ElevenLabs speech character '{character}'. Supported characters: {supported}")
        return entry.character

    def _create_ssl_context(self) -> ssl.SSLContext:
        if certifi is None:
            return ssl.create_default_context()
        return ssl.create_default_context(cafile=certifi.where())

    def _read_error(self, exc: HTTPError) -> str:
        raw_body = exc.read().decode("utf-8", errors="replace")
        if not raw_body:
            return f"ElevenLabs returned HTTP {exc.code}"

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return f"ElevenLabs returned HTTP {exc.code}: {raw_body}"

        detail = payload.get("detail")
        if isinstance(detail, dict):
            message = detail.get("message") or detail.get("status")
            if message:
                return f"ElevenLabs returned HTTP {exc.code}: {message}"
        if isinstance(detail, str):
            return f"ElevenLabs returned HTTP {exc.code}: {detail}"
        return f"ElevenLabs returned HTTP {exc.code}: {raw_body}"
