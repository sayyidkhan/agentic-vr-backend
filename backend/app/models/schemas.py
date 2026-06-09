from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: str
    engine: str
    databasePath: Optional[str] = None
    sqliteVersion: Optional[str] = None
    quickCheck: Optional[str] = None
    journalMode: Optional[str] = None
    schemaRevision: Optional[str] = None
    tableCount: Optional[int] = None


class VideoMetadata(BaseModel):
    videoId: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None


class AnalyzeSceneRequest(BaseModel):
    frame: Optional[str] = None
    timestamp: float = Field(ge=0)
    transcriptSegment: Optional[str] = None
    videoMetadata: VideoMetadata = Field(default_factory=VideoMetadata)


class Character(BaseModel):
    characterId: str
    sceneId: str
    name: str
    role: str
    personality: str
    emotionalState: str
    goals: list[str]
    knowledgeBoundaries: list[str]
    speakingStyle: str


class Scene(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sceneId: str
    videoId: str
    timestamp: float
    frameRef: Optional[str] = None
    transcriptSegment: Optional[str] = None
    summary: str
    setting: str
    emotionalTone: str
    conflict: str
    objects: list[str]
    characters: list[Character]
    directorContext: str
    memorySummary: str
    createdAt: Optional[datetime] = None


class AgentTraceStep(BaseModel):
    step: str
    agent: str
    status: Literal["pending", "complete", "fallback", "error"]
    detail: Optional[str] = None


class AnalyzeSceneResponse(BaseModel):
    sceneId: str
    sceneSummary: str
    scene: Scene
    characters: list[Character]
    directorContext: str
    memorySummary: str
    agentTrace: list[AgentTraceStep]


class ChatRequest(BaseModel):
    sceneId: str
    message: str = Field(min_length=1)
    targetAgentId: Optional[str] = None


class RespondingAgent(BaseModel):
    id: str
    name: str
    type: Literal["character", "director", "research", "fallback"]


class ChatResponse(BaseModel):
    respondingAgent: RespondingAgent
    response: str
    updatedMemorySummary: str
    agentTrace: list[AgentTraceStep]


class ResearchRequest(BaseModel):
    sceneId: str
    query: str = Field(min_length=1)


class ResearchSource(BaseModel):
    title: str
    url: str
    snippet: str


class ResearchResponse(BaseModel):
    summary: str
    sources: list[ResearchSource]
    recommendedContext: str


class CheckoutRequest(BaseModel):
    sceneId: str
    unlockType: str = "premium_scene"


class CheckoutResponse(BaseModel):
    checkoutUrl: str
    mode: Literal["stripe", "simulated"]
