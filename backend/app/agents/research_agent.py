from app.models.schemas import ResearchResponse, ResearchSource


class ResearchAgent:
    def search(self, query: str) -> ResearchResponse:
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
