from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings
from app.models.schemas import SpeechCharacterPreset

try:
    import certifi
except ImportError:  # pragma: no cover - certifi is expected through requests/httpx dependencies.
    certifi = None


CHARACTER_SCRIPTS: dict[str, str] = {
    "yoda": "Ready for the demo, we are. Strong with SceneVerse, this experience is.",
    "vader": "The scene is now under my command. Do not underestimate the power of this experience.",
}

CHARACTER_LABELS: dict[str, str] = {
    "yoda": "Yoda",
    "vader": "Darth Vader",
}


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

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ssl_context = self._create_ssl_context()

    def list_character_presets(self) -> list[SpeechCharacterPreset]:
        return [
            SpeechCharacterPreset(
                character=character,
                label=CHARACTER_LABELS[character],
                predefinedText=CHARACTER_SCRIPTS[character],
                voiceIdConfigured=self._voice_id_for(character) is not None,
            )
            for character in CHARACTER_SCRIPTS
        ]

    def synthesize_predefined(self, character: str) -> SpeechAudio:
        normalized_character = self._normalize_character(character)
        return self.synthesize(character=normalized_character, text=CHARACTER_SCRIPTS[normalized_character])

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
            env_name = f"ELEVENLABS_{normalized_character.upper()}_VOICE_ID"
            raise ElevenLabsConfigurationError(f"{env_name} is not configured")

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
        voices = {
            "yoda": self.settings.elevenlabs_yoda_voice_id,
            "vader": self.settings.elevenlabs_vader_voice_id,
        }
        voice_id = voices.get(character)
        if voice_id is None:
            return None
        return voice_id.strip() or None

    def _normalize_character(self, character: str) -> str:
        normalized = character.strip().lower()
        if normalized not in CHARACTER_SCRIPTS:
            supported = ", ".join(sorted(CHARACTER_SCRIPTS))
            raise ValueError(f"Unsupported speech character '{character}'. Supported characters: {supported}")
        return normalized

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
