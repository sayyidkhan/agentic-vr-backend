from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: str
    engine: str
    environment: str
    databasePath: Optional[str] = None
    sqliteVersion: Optional[str] = None
    quickCheck: Optional[str] = None
    journalMode: Optional[str] = None
    schemaRevision: Optional[str] = None
    tableCount: Optional[int] = None


class DatabaseTableContentsResponse(BaseModel):
    table: str
    columns: list[str]
    limit: int
    offset: int
    rowCount: int
    rows: list[dict[str, Any]]


class BedrockProbeRequest(BaseModel):
    prompt: str = "Reply with the exact token BEDROCK_OK and one short sentence."


class BedrockProbeResponse(BaseModel):
    status: Literal["ok", "error"]
    provider: str
    modelId: str
    region: str
    prompt: str
    outputText: Optional[str] = None
    errorType: Optional[str] = None
    errorMessage: Optional[str] = None


class ModelProbeRequest(BaseModel):
    modelKey: Optional[str] = None
    prompt: str = "Reply with the exact token MODEL_OK and one short sentence."


class ModelProbeResponse(BaseModel):
    status: Literal["ok", "error"]
    modelKey: str
    label: str
    provider: str
    transport: Literal["bedrock", "openai"]
    modelId: str
    region: Optional[str] = None
    prompt: str
    outputText: Optional[str] = None
    errorType: Optional[str] = None
    errorMessage: Optional[str] = None


class ModelProbeBatchResponse(BaseModel):
    status: Literal["ok", "partial", "error"]
    prompt: str
    results: list[ModelProbeResponse]


class EnabledModelResponse(BaseModel):
    key: str
    label: str
    provider: str
    transport: Literal["bedrock", "openai"]
    modelId: str
    region: Optional[str] = None
    enabled: bool
    credentialSource: str
    credentialConfigured: bool


class ModelCatalogResponse(BaseModel):
    defaultModelKey: str
    models: list[EnabledModelResponse]


class RealtimeTurnDetection(BaseModel):
    type: Literal["server_vad"]
    threshold: float
    prefixPaddingMs: int
    silenceDurationMs: int


class RealtimeTranscriptionTokenResponse(BaseModel):
    value: str
    expiresAt: int
    model: str
    provider: Literal["openai"]
    turnDetection: RealtimeTurnDetection


class SpeechCharacterPreset(BaseModel):
    character: str
    label: str
    predefinedText: str
    voiceIdConfigured: bool


class SpeechCharacterListResponse(BaseModel):
    provider: Literal["elevenlabs", "speechmatics", "hybrid"]
    modelId: str
    outputFormat: str
    apiKeyConfigured: bool
    characters: list[SpeechCharacterPreset]


class SpeechSynthesisRequest(BaseModel):
    character: str = Field(min_length=1, max_length=80)
    text: Optional[str] = Field(default=None, min_length=1, max_length=3000)


class VideoMetadata(BaseModel):
    videoId: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None


class VideoAsset(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    videoId: str
    sourceType: Literal["upload", "youtube", "external_url"]
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    originalUrl: Optional[str] = None
    originalFilename: Optional[str] = None
    storageBackend: Optional[str] = None
    storageKey: Optional[str] = None
    playbackUrl: Optional[str] = None
    contentType: Optional[str] = None
    fileSizeBytes: Optional[int] = None
    status: str
    createdAt: datetime
    updatedAt: datetime


class VideoListResponse(BaseModel):
    items: list[VideoAsset]
    limit: int
    offset: int
    rowCount: int


class CreateVideoLinkRequest(BaseModel):
    url: str = Field(min_length=1)
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    sourceType: Literal["youtube", "external_url"] = "youtube"


class UpdateVideoRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    status: Optional[str] = None


class DeleteVideoResponse(BaseModel):
    deleted: bool
    videoId: str


class AnalyzeSceneRequest(BaseModel):
    frame: Optional[str] = None
    timestamp: float = Field(ge=0)
    transcriptSegment: Optional[str] = None
    videoMetadata: VideoMetadata = Field(default_factory=VideoMetadata)


class CharacterProfileSource(BaseModel):
    title: str
    url: str
    snippet: str


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
    franchise: Optional[str] = None
    portrayedBy: Optional[str] = None
    identificationConfidence: Optional[float] = None
    profileSummary: Optional[str] = None
    profileSources: list[CharacterProfileSource] = Field(default_factory=list)


class NewCharacterSessionRequest(BaseModel):
    sceneId: str
    characterId: Optional[str] = None


class NewCharacterSessionResponse(BaseModel):
    characterSessionId: str
    sceneId: str
    character: Character
    openingMessage: str
    memorySummary: str
    suggestedPrompts: list[str]


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
    detectedWorkTitle: Optional[str] = None
    detectedUniverse: Optional[str] = None
    analysisMode: Optional[Literal["live", "fallback"]] = None


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
    analysisMode: Literal["live", "fallback"]
    sourceModelId: Optional[str] = None


class ChatRequest(BaseModel):
    sceneId: str
    message: str = Field(min_length=1)
    targetAgentId: Optional[str] = None


class CharacterRouterRequest(BaseModel):
    sceneId: str
    message: str = Field(min_length=1)
    targetAgentId: Optional[str] = None


class CharacterChatRequest(BaseModel):
    sceneId: str
    message: str = Field(min_length=1)
    characterId: Optional[str] = None


class RespondingAgent(BaseModel):
    id: str
    name: str
    type: Literal["character", "director", "research", "fallback"]


class CharacterRouterResponse(BaseModel):
    sceneId: str
    targetAgent: RespondingAgent
    reason: str
    confidence: float = Field(ge=0, le=1)
    agentTrace: list[AgentTraceStep]


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
