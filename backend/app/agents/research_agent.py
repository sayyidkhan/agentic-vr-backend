from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.config import Settings
from app.models.schemas import ResearchResponse, ResearchSource


class ResearchAgent:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def search(self, query: str) -> ResearchResponse:
        if self.settings and self.settings.exa_api_key:
            live_response = self._search_with_exa(query)
            if live_response is not None:
                return live_response

        summary = (
            "External research is not connected yet, so this fallback summarizes the likely public-context path. "
            "Wire EXA_API_KEY next to retrieve live cinematic references, genre context, or production trivia."
        )
        return ResearchResponse(
            summary=summary,
            sources=[
                ResearchSource(
                    title="Exa integration placeholder",
                    url="https://exa.ai",
                    snippet="Fallback source returned until EXA_API_KEY is configured.",
                )
            ],
            recommendedContext=f"Use external context only in Director Agent responses for query: {query}",
        )

    def _search_with_exa(self, query: str) -> ResearchResponse | None:
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
        for citation in body.get("citations", [])[:5]:
            url = citation.get("url")
            title = citation.get("title")
            if not url or not title:
                continue
            sources.append(
                ResearchSource(
                    title=title,
                    url=url,
                    snippet=(citation.get("text") or "")[:280],
                )
            )

        return ResearchResponse(
            summary=answer.strip(),
            sources=sources or [
                ResearchSource(
                    title="Exa answer",
                    url="https://docs.exa.ai/reference/answer",
                    snippet="Live Exa answer returned without explicit citations.",
                )
            ],
            recommendedContext=f"Use externally researched context carefully for query: {query}",
        )
