from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.config import Settings
from app.models.schemas import RealtimeTranscriptionTokenResponse, RealtimeTurnDetection


class OpenAIRealtimeError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenAIRealtimeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_transcription_token(self) -> RealtimeTranscriptionTokenResponse:
        if not self.settings.openai_api_key:
            raise OpenAIRealtimeError("OPENAI_API_KEY is not configured for realtime transcription.", 503)

        turn_detection = {
            "type": "server_vad",
            "threshold": self.settings.openai_realtime_vad_threshold,
            "prefix_padding_ms": self.settings.openai_realtime_vad_prefix_padding_ms,
            "silence_duration_ms": self.settings.openai_realtime_vad_silence_duration_ms,
        }
        payload = json.dumps(
            {
                "expires_after": {
                    "anchor": "created_at",
                    "seconds": self.settings.openai_realtime_token_ttl_seconds,
                },
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": 24000},
                            "noise_reduction": {"type": "near_field"},
                            "transcription": {
                                "model": self.settings.openai_realtime_transcription_model,
                                "language": "en",
                                "prompt": "SceneVerse voice commands, character names, video controls, and cinematic scene questions.",
                            },
                            "turn_detection": turn_detection,
                        }
                    },
                },
            }
        ).encode("utf-8")

        request = urllib_request.Request(
            "https://api.openai.com/v1/realtime/client_secrets",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.openai_api_key}",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OpenAIRealtimeError(f"OpenAI realtime token request failed: HTTP {exc.code} {body}") from exc
        except urllib_error.URLError as exc:
            raise OpenAIRealtimeError(f"OpenAI realtime token request failed: {exc.reason}") from exc

        client_secret = body.get("client_secret") if isinstance(body.get("client_secret"), dict) else {}
        value = body.get("value") or client_secret.get("value")
        expires_at = body.get("expires_at") or client_secret.get("expires_at")
        if not isinstance(value, str) or not isinstance(expires_at, int):
            raise OpenAIRealtimeError("OpenAI realtime token response did not include a usable client secret.")

        return RealtimeTranscriptionTokenResponse(
            value=value,
            expiresAt=expires_at,
            model=self.settings.openai_realtime_transcription_model,
            provider="openai",
            turnDetection=RealtimeTurnDetection(
                type="server_vad",
                threshold=self.settings.openai_realtime_vad_threshold,
                prefixPaddingMs=self.settings.openai_realtime_vad_prefix_padding_ms,
                silenceDurationMs=self.settings.openai_realtime_vad_silence_duration_ms,
            ),
        )
