from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib import request as urllib_request

import boto3

from app.config import Settings


@dataclass
class LiveSceneAnalysisResult:
    payload: dict[str, Any]
    model_id: str


class SceneAnalysisService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze(self, *, frame_data_url: str, transcript_segment: str | None, video_title: str | None) -> LiveSceneAnalysisResult:
        image_format, image_bytes = self._decode_data_url(frame_data_url)
        prompt = self._build_prompt(transcript_segment=transcript_segment, video_title=video_title)

        if self.settings.bedrock_api_key:
            response = self._converse_with_bearer_token(prompt=prompt, image_format=image_format, image_bytes=image_bytes)
        else:
            response = self._converse_with_boto3(prompt=prompt, image_format=image_format, image_bytes=image_bytes)

        text_output = self._extract_text(response)
        parsed = self._extract_json_payload(text_output)
        return LiveSceneAnalysisResult(payload=parsed, model_id=self.settings.scene_analysis_model_id)

    def _converse_with_boto3(self, *, prompt: str, image_format: str, image_bytes: bytes) -> dict[str, Any]:
        client = boto3.client("bedrock-runtime", region_name=self.settings.bedrock_region)
        return client.converse(
            modelId=self.settings.scene_analysis_model_id,
            system=[{"text": "You are a precise film-scene analysis engine. Return JSON only."}],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                        {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 1800, "temperature": 0.1},
        )

    def _converse_with_bearer_token(self, *, prompt: str, image_format: str, image_bytes: bytes) -> dict[str, Any]:
        payload = json.dumps(
            {
                "system": [{"text": "You are a precise film-scene analysis engine. Return JSON only."}],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt},
                            {
                                "image": {
                                    "format": image_format,
                                    "source": {"bytes": base64.b64encode(image_bytes).decode("ascii")},
                                }
                            },
                        ],
                    }
                ],
                "inferenceConfig": {"maxTokens": 1800, "temperature": 0.1},
            }
        ).encode("utf-8")
        request = urllib_request.Request(
            (
                f"https://bedrock-runtime.{self.settings.bedrock_region}.amazonaws.com/"
                f"model/{self.settings.scene_analysis_model_id}/converse"
            ),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.bedrock_api_key}",
            },
            method="POST",
        )
        with urllib_request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build_prompt(self, *, transcript_segment: str | None, video_title: str | None) -> str:
        transcript_hint = transcript_segment or "No transcript provided."
        title_hint = video_title or "Unknown title"
        return (
            "Analyze this movie frame and return JSON only with the exact schema keys below. "
            "Be conservative. If you are unsure about a character identity, use a descriptive name instead of inventing. "
            "If you recognize the film or franchise, include it. "
            "Schema: "
            "{"
            "\"detectedWorkTitle\": string|null, "
            "\"detectedUniverse\": string|null, "
            "\"sceneSummary\": string, "
            "\"setting\": string, "
            "\"emotionalTone\": string, "
            "\"conflict\": string, "
            "\"objects\": string[], "
            "\"directorContext\": string, "
            "\"characters\": ["
            "{"
            "\"name\": string, "
            "\"franchise\": string|null, "
            "\"portrayedBy\": string|null, "
            "\"confidence\": number, "
            "\"role\": string, "
            "\"personality\": string, "
            "\"emotionalState\": string, "
            "\"goals\": string[], "
            "\"knowledgeBoundaries\": string[], "
            "\"speakingStyle\": string, "
            "\"box\": [number, number, number, number]"
            "}"
            "]"
            "}. "
            "box is the tight bounding box around the character's full visible body in this exact frame, "
            "as [left, top, right, bottom] normalized to 0-1 relative to the frame width and height. "
            "Include every visually present character, even partial foreground silhouettes or small distant figures. "
            f"Limit to at most {self.settings.scene_analysis_max_characters} characters. "
            f"Video title hint: {title_hint}. "
            f"Transcript hint: {transcript_hint}."
        )

    def _decode_data_url(self, data_url: str) -> tuple[str, bytes]:
        match = re.match(r"^data:(image/[-+.\w]+);base64,(.+)$", data_url, re.DOTALL)
        if not match:
            raise ValueError("Frame must be a base64 data URL like data:image/jpeg;base64,...")
        mime_type = match.group(1).lower()
        encoded = match.group(2)
        image_format = {
            "image/jpeg": "jpeg",
            "image/jpg": "jpeg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }.get(mime_type)
        if image_format is None:
            raise ValueError(f"Unsupported image MIME type: {mime_type}")
        return image_format, base64.b64decode(encoded)

    def _extract_text(self, response: dict[str, Any]) -> str:
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        text_parts = [block.get("text", "") for block in blocks if block.get("text")]
        return "\n".join(text_parts).strip()

    def _extract_json_payload(self, text_output: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", text_output, re.DOTALL)
        if not match:
            raise ValueError("Scene analysis response did not contain JSON")
        return json.loads(match.group(0))
