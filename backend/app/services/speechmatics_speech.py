from __future__ import annotations

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings
from app.services.elevenlabs_speech import CHARACTER_SCRIPTS, SpeechAudio

try:
    import certifi
except ImportError:  # pragma: no cover - certifi is expected through requests/httpx dependencies.
    certifi = None


class SpeechmaticsConfigurationError(Exception):
    pass


class SpeechmaticsSpeechError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class SpeechmaticsSpeechService:
    base_url = "https://preview.tts.speechmatics.com/generate"
    model_id = "speechmatics-preview-tts"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ssl_context = self._create_ssl_context()

    def synthesize_predefined(self, character: str) -> SpeechAudio:
        normalized_character = self._normalize_character(character)
        return self.synthesize(character=normalized_character, text=CHARACTER_SCRIPTS[normalized_character])

    def synthesize(self, character: str, text: str) -> SpeechAudio:
        normalized_character = self._normalize_character_name(character)
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Speech text must not be empty")

        api_key = self.settings.speechmatics_api_key
        if not api_key:
            raise SpeechmaticsConfigurationError("SPEECHMATICS_API_KEY is not configured")

        voice_id = self.settings.speechmatics_tts_voice_id.strip()
        if not voice_id:
            raise SpeechmaticsConfigurationError("SPEECHMATICS_TTS_VOICE_ID is not configured")
        output_format = self.settings.speechmatics_tts_output_format
        query = urlencode({"output_format": output_format})
        request = Request(
            url=f"{self.base_url}/{voice_id}?{query}",
            data=json.dumps({"text": normalized_text}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/wav",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=30, context=self._ssl_context) as response:
                return SpeechAudio(
                    character=normalized_character,
                    provider="speechmatics",
                    voice_id=voice_id,
                    model_id=self.model_id,
                    output_format=output_format,
                    text=normalized_text,
                    content=response.read(),
                )
        except HTTPError as exc:
            status_code = 503 if exc.code in {401, 403} else 502
            raise SpeechmaticsSpeechError(self._read_error(exc), status_code=status_code) from exc
        except URLError as exc:
            raise SpeechmaticsSpeechError(f"Speechmatics TTS request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SpeechmaticsSpeechError("Speechmatics TTS request timed out") from exc

    def _normalize_character(self, character: str) -> str:
        normalized = character.strip().lower()
        if normalized not in CHARACTER_SCRIPTS:
            supported = ", ".join(sorted(CHARACTER_SCRIPTS))
            raise ValueError(f"Unsupported speech character '{character}'. Supported characters: {supported}")
        return normalized

    def _normalize_character_name(self, character: str) -> str:
        normalized = character.strip().lower().replace(" ", "_")
        if not normalized:
            raise ValueError("Speech character must not be empty")
        return "".join(char for char in normalized if char.isalnum() or char in {"_", "-"}).strip("_-") or "character"

    def _create_ssl_context(self) -> ssl.SSLContext:
        if certifi is None:
            return ssl.create_default_context()
        return ssl.create_default_context(cafile=certifi.where())

    def _read_error(self, exc: HTTPError) -> str:
        raw_body = exc.read().decode("utf-8", errors="replace")
        if not raw_body:
            return f"Speechmatics TTS returned HTTP {exc.code}"
        return f"Speechmatics TTS returned HTTP {exc.code}: {raw_body}"
