from contextlib import asynccontextmanager
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import MetaData, Table, func, inspect, select, text
from sqlalchemy.orm import Session

from app.agents.orchestrator import OrchestratorAgent
from app.agents.research_agent import ResearchAgent
from app.agents.scene_parser import SceneParserAgent
from app.config import get_settings
from app.database import MANAGED_TABLES, get_db, init_db
from app.models.schemas import (
    AnalyzeSceneRequest,
    AnalyzeSceneResponse,
    BedrockProbeRequest,
    BedrockProbeResponse,
    ChatRequest,
    ChatResponse,
    CreateVideoLinkRequest,
    DatabaseTableContentsResponse,
    CheckoutRequest,
    CheckoutResponse,
    DatabaseHealthResponse,
    EnabledModelResponse,
    ModelCatalogResponse,
    ModelProbeBatchResponse,
    ModelProbeRequest,
    ModelProbeResponse,
    RealtimeTranscriptionTokenResponse,
    VideoAsset,
    VideoListResponse,
    HealthResponse,
    NewCharacterSessionRequest,
    NewCharacterSessionResponse,
    ResearchRequest,
    ResearchResponse,
)
from app.services.bedrock_runtime import BedrockRuntimeService
from app.services.checkout import CheckoutError, CheckoutService, StripeWebhookError
from app.services.model_runtime import ModelRuntimeService
from app.services.openai_realtime import OpenAIRealtimeError, OpenAIRealtimeService
from app.services.video_storage import VideoStorageService
from app.store.sqlite_store import SQLiteStore

settings = get_settings()
Path(settings.media_local_dir).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials="*" not in settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount(settings.media_public_path, StaticFiles(directory=settings.media_local_dir), name="media")

research_agent = ResearchAgent(settings=settings)
scene_parser = SceneParserAgent(settings=settings)
orchestrator = OrchestratorAgent(settings=settings, research_agent=research_agent)
bedrock_runtime = BedrockRuntimeService(settings=settings)
model_runtime = ModelRuntimeService(settings=settings)
checkout_service = CheckoutService(settings=settings)
openai_realtime_service = OpenAIRealtimeService(settings=settings)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.environment)


@app.post("/api/bedrock/test", response_model=BedrockProbeResponse)
def test_bedrock_connection(payload: BedrockProbeRequest | None = None) -> BedrockProbeResponse:
    request = payload or BedrockProbeRequest()
    return bedrock_runtime.probe(request.prompt)


@app.get("/api/models", response_model=ModelCatalogResponse)
def list_configured_models() -> ModelCatalogResponse:
    return model_runtime.list_models()


@app.post("/api/models/test", response_model=ModelProbeResponse)
def test_configured_model(payload: ModelProbeRequest | None = None) -> ModelProbeResponse:
    request = payload or ModelProbeRequest()
    try:
        return model_runtime.probe(prompt=request.prompt, model_key=request.modelKey)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/models/test-all", response_model=ModelProbeBatchResponse)
def test_all_configured_models(payload: ModelProbeRequest | None = None) -> ModelProbeBatchResponse:
    request = payload or ModelProbeRequest()
    return model_runtime.probe_all(prompt=request.prompt)


@app.post("/api/realtime/transcription-token", response_model=RealtimeTranscriptionTokenResponse)
def create_realtime_transcription_token() -> RealtimeTranscriptionTokenResponse:
    try:
        return openai_realtime_service.create_transcription_token()
    except OpenAIRealtimeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/health/db", response_model=DatabaseHealthResponse)
def database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    database = settings.database_url.split(":", 1)[0]

    try:
        db.execute(text("SELECT 1"))

        schema_revision = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
        table_count = len(inspect(db.bind).get_table_names()) if db.bind is not None else None

        if not settings.database_url.startswith("sqlite"):
            return DatabaseHealthResponse(
                status="ok",
                database=database,
                engine="sqlalchemy",
                schemaRevision=schema_revision,
                tableCount=table_count,
            )

        sqlite_version = db.execute(text("SELECT sqlite_version()")).scalar_one()
        quick_check = db.execute(text("PRAGMA quick_check")).scalar_one()
        journal_mode = db.execute(text("PRAGMA journal_mode")).scalar_one()
        database_path = db.execute(text("PRAGMA database_list")).mappings().first()
        resolved_database_path = None
        if database_path is not None:
            resolved_database_path = database_path["file"] or ":memory:"

        return DatabaseHealthResponse(
            status="ok",
            database="sqlite",
            engine="sqlalchemy",
            databasePath=resolved_database_path,
            sqliteVersion=sqlite_version,
            quickCheck=quick_check,
            journalMode=journal_mode,
            schemaRevision=schema_revision,
            tableCount=table_count,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database health check failed: {exc}") from exc


@app.get("/", response_model=HealthResponse)
def root() -> HealthResponse:
    return health()


def _find_character(scene, character_id: str | None):
    if character_id:
        for character in scene.characters:
            if character.characterId == character_id:
                return character
        raise HTTPException(status_code=404, detail=f"Character not found in scene: {character_id}")

    if not scene.characters:
        raise HTTPException(status_code=404, detail="No characters found for scene")

    return scene.characters[0]


def _serialize_debug_value(column_name: str, value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str) and column_name.endswith("_json"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


@app.get("/api/db/{table_name}", response_model=DatabaseTableContentsResponse)
def database_table_contents(
    table_name: str,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DatabaseTableContentsResponse:
    inspector = inspect(db.bind)
    table_names = set(inspector.get_table_names()) if db.bind is not None else set()

    if table_name not in table_names:
        raise HTTPException(status_code=404, detail=f"Table not found: {table_name}")

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=db.bind)

    total_rows = db.execute(select(func.count()).select_from(table)).scalar_one()

    order_column = None
    for candidate in ("created_at", f"{table_name[:-1]}_id", "scene_id"):
        if candidate in table.c:
            order_column = table.c[candidate]
            break

    query = select(table)
    if order_column is not None:
        query = query.order_by(order_column.desc())
    query = query.limit(limit).offset(offset)

    rows = []
    for row in db.execute(query).mappings().all():
        rows.append({key: _serialize_debug_value(key, value) for key, value in row.items()})

    return DatabaseTableContentsResponse(
        table=table_name,
        columns=[column.name for column in table.columns],
        limit=limit,
        offset=offset,
        rowCount=total_rows,
        rows=rows,
    )


@app.get("/api/videos", response_model=VideoListResponse)
def list_videos(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> VideoListResponse:
    items, total = SQLiteStore(db).list_videos(limit=limit, offset=offset)
    return VideoListResponse(items=items, limit=limit, offset=offset, rowCount=total)


@app.get("/api/videos/{video_id}", response_model=VideoAsset)
def get_video(video_id: str, db: Session = Depends(get_db)) -> VideoAsset:
    video = SQLiteStore(db).get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@app.post("/api/videos/link", response_model=VideoAsset, status_code=status.HTTP_201_CREATED)
def create_video_link(payload: CreateVideoLinkRequest, db: Session = Depends(get_db)) -> VideoAsset:
    return SQLiteStore(db).create_video_link(url=payload.url, source_type=payload.sourceType, title=payload.title)


@app.post("/api/videos/upload", response_model=VideoAsset, status_code=status.HTTP_201_CREATED)
def upload_video(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> VideoAsset:
    video_id = f"video_{uuid4().hex[:12]}"
    stored_video = VideoStorageService(settings).store_upload(file, video_id=video_id)
    return SQLiteStore(db).create_uploaded_video(
        video_id=video_id,
        title=title,
        original_filename=file.filename,
        storage_backend=stored_video.storage_backend,
        storage_key=stored_video.storage_key,
        playback_url=stored_video.playback_url,
        content_type=stored_video.content_type,
        file_size_bytes=stored_video.file_size_bytes,
    )


@app.post("/api/scenes/analyze", response_model=AnalyzeSceneResponse)
def analyze_scene(payload: AnalyzeSceneRequest, db: Session = Depends(get_db)) -> AnalyzeSceneResponse:
    result = scene_parser.analyze(payload)
    SQLiteStore(db).save_scene(result.scene)
    return result


@app.post("/api/character/new", response_model=NewCharacterSessionResponse)
def create_character_session(payload: NewCharacterSessionRequest, db: Session = Depends(get_db)) -> NewCharacterSessionResponse:
    store = SQLiteStore(db)
    scene = store.get_scene(payload.sceneId)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    character = _find_character(scene, payload.characterId)
    session_id = store.create_character_session(scene.sceneId, character.characterId)
    opening_message = orchestrator.character_agent.opening_message(scene, character, scene.memorySummary)

    return NewCharacterSessionResponse(
        characterSessionId=session_id,
        sceneId=scene.sceneId,
        character=character,
        openingMessage=opening_message,
        memorySummary=scene.memorySummary,
        suggestedPrompts=[
            f"What are you trying to do right now, {character.name}?",
            f"Who do you trust the least in this scene?",
            "What are you not telling me yet?",
        ],
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    store = SQLiteStore(db)
    scene = store.get_scene(payload.sceneId)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    result = orchestrator.respond(scene=scene, message=payload.message, target_agent_id=payload.targetAgentId)
    store.save_turn(payload.sceneId, payload.message, result.response)
    store.update_memory_summary(payload.sceneId, result.response.updatedMemorySummary)

    if result.research_summary:
        store.save_research(payload.sceneId, payload.message, result.research_summary)

    return result.response


@app.post("/api/research", response_model=ResearchResponse)
def research(payload: ResearchRequest, db: Session = Depends(get_db)) -> ResearchResponse:
    store = SQLiteStore(db)
    scene = store.get_scene(payload.sceneId)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    result = research_agent.search(payload.query)
    store.save_research(payload.sceneId, payload.query, result.summary)
    return result


@app.post("/api/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)) -> CheckoutResponse:
    scene = SQLiteStore(db).get_scene(payload.sceneId)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        return checkout_service.create_checkout(payload)
    except CheckoutError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict[str, str | bool]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    try:
        event = checkout_service.construct_webhook_event(payload=payload, signature=signature)
    except CheckoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StripeWebhookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"received": True, "eventType": event.get("type", "unknown")}
