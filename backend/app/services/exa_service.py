from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.config import Settings
from app.models.schemas import CharacterProfileSource


@dataclass
class ExaCharacterProfile:
    summary: str
    sources: list[CharacterProfileSource]


class ExaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_character_profile(self, *, character_name: str, work_title: str | None, franchise: str | None) -> Optional[ExaCharacterProfile]:
        if not self.settings.exa_api_key or not self.settings.enable_exa_character_enrichment:
            return None

        query_parts = [
            f"Who is {character_name}",
            f"in {work_title}" if work_title else "",
            f"from {franchise}" if franchise and franchise != work_title else "",
            "Give a concise character profile with role, personality, motivations, and speaking style.",
        ]
        query = " ".join(part for part in query_parts if part).strip()
        payload = json.dumps({"query": query, "text": False}).encode("utf-8")
        request = urllib_request.Request(
            "https://api.exa.ai/answer",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.settings.exa_api_key,
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib_error.HTTPError, urllib_error.URLError, TimeoutError, json.JSONDecodeError):
            return None

        answer = body.get("answer")
        if not answer:
            return None

        sources = []
        for citation in body.get("citations", [])[:3]:
            url = citation.get("url")
            title = citation.get("title")
            if not url or not title:
                continue
            sources.append(
                CharacterProfileSource(
                    title=title,
                    url=url,
                    snippet=(citation.get("text") or "")[:280],
                )
            )

        return ExaCharacterProfile(summary=answer.strip(), sources=sources)
