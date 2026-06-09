from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.agents.character_agent import CharacterAgent
from app.agents.director_agent import DirectorAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.research_agent import ResearchAgent
from app.models.schemas import AgentTraceStep, ChatResponse, RespondingAgent, Scene


@dataclass
class OrchestrationResult:
    response: ChatResponse
    research_summary: Optional[str] = None


class OrchestratorAgent:
    def __init__(self, research_agent: ResearchAgent | None = None) -> None:
        self.character_agent = CharacterAgent()
        self.director_agent = DirectorAgent()
        self.memory_agent = MemoryAgent()
        self.research_agent = research_agent or ResearchAgent()

    def respond(self, scene: Scene, message: str, target_agent_id: Optional[str]) -> OrchestrationResult:
        trace = [
            AgentTraceStep(step="classify_intent", agent="orchestrator", status="complete"),
            AgentTraceStep(step="load_memory", agent="memory", status="complete"),
        ]
        route = self._classify(message, target_agent_id)
        research_summary = None

        if route == "research":
            trace.append(AgentTraceStep(step="search_external_context", agent="research", status="fallback"))
            research_summary = self.research_agent.search(message).summary
            response_text = self.director_agent.respond(
                scene=scene,
                message=message,
                memory_summary=scene.memorySummary,
                research_summary=research_summary,
            )
            responding = RespondingAgent(id="director", name="Director Agent", type="director")
            trace.append(AgentTraceStep(step="respond_with_research", agent="director", status="complete"))
        elif route == "director":
            response_text = self.director_agent.respond(
                scene=scene,
                message=message,
                memory_summary=scene.memorySummary,
            )
            responding = RespondingAgent(id="director", name="Director Agent", type="director")
            trace.append(AgentTraceStep(step="respond", agent="director", status="complete"))
        else:
            character = self._select_character(scene, target_agent_id)
            response_text = self.character_agent.respond(scene, character, message, scene.memorySummary)
            response_text = self.director_agent.validate_character_response(response_text)
            responding = RespondingAgent(id=character.characterId, name=character.name, type="character")
            trace.append(AgentTraceStep(step="respond", agent=character.name, status="complete"))
            trace.append(AgentTraceStep(step="validate_consistency", agent="director", status="complete"))

        updated_summary = self.memory_agent.update_summary(scene.memorySummary, message, responding.name)
        trace.append(AgentTraceStep(step="update_memory", agent="memory", status="complete"))

        return OrchestrationResult(
            response=ChatResponse(
                respondingAgent=responding,
                response=response_text,
                updatedMemorySummary=updated_summary,
                agentTrace=trace,
            ),
            research_summary=research_summary,
        )

    def _classify(self, message: str, target_agent_id: Optional[str]) -> str:
        normalized = message.lower()
        if target_agent_id == "director":
            return "director"

        research_terms = ("real event", "trivia", "reference", "genre", "inspired by", "based on")
        if any(term in normalized for term in research_terms):
            return "research"

        director_terms = ("director", "meaning", "symbol", "cinematic", "story", "really happening", "theme")
        if any(term in normalized for term in director_terms):
            return "director"

        return "character"

    def _select_character(self, scene: Scene, target_agent_id: Optional[str]):
        if target_agent_id:
            for character in scene.characters:
                if character.characterId == target_agent_id:
                    return character

        return scene.characters[0]
