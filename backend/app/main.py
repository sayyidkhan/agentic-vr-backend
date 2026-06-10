from contextlib import asynccontextmanager
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import MetaData, Table, func, inspect, select, text
from sqlalchemy.orm import Session

from app.agents.orchestrator import OrchestratorAgent
from app.agents.character_router_agent import CharacterRouterAgent
from app.agents.research_agent import ResearchAgent
from app.agents.scene_parser import SceneParserAgent
from app.config import get_settings
from app.database import MANAGED_TABLES, get_db, init_db
from app.models.schemas import (
    AnalyzeSceneRequest,
    AnalyzeSceneResponse,
    AgentTraceStep,
    BedrockProbeRequest,
    BedrockProbeResponse,
    ChatRequest,
    ChatResponse,
    CharacterChatRequest,
    CharacterRouterRequest,
    CharacterRouterResponse,
    CreateVideoLinkRequest,
    DatabaseTableContentsResponse,
    CheckoutRequest,
    CheckoutResponse,
    DatabaseHealthResponse,
    DeleteVideoResponse,
    EnabledModelResponse,
    ModelCatalogResponse,
    ModelProbeBatchResponse,
    ModelProbeRequest,
    ModelProbeResponse,
    RealtimeTranscriptionTokenResponse,
    SpeechCharacterListResponse,
    SpeechCharacterPreset,
    SpeechSynthesisRequest,
    VideoAsset,
    VideoListResponse,
    HealthResponse,
    NewCharacterSessionRequest,
    NewCharacterSessionResponse,
    ResearchRequest,
    ResearchResponse,
    UpdateVideoRequest,
)
from app.services.bedrock_runtime import BedrockRuntimeService
from app.services.checkout import CheckoutError, CheckoutService, StripeWebhookError
from app.services.elevenlabs_speech import (
    ElevenLabsConfigurationError,
    ElevenLabsSpeechError,
    ElevenLabsSpeechService,
)
from app.services.model_runtime import ModelRuntimeService
from app.services.openai_realtime import OpenAIRealtimeError, OpenAIRealtimeService
from app.services.speechmatics_speech import (
    SpeechmaticsConfigurationError,
    SpeechmaticsSpeechError,
    SpeechmaticsSpeechService,
)
from app.services.voice_registry import VoiceRegistryService
from app.services.video_storage import VideoStorageService
from app.store.sqlite_store import DuplicateVideoReferenceError, SQLiteStore

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
character_router = CharacterRouterAgent()
bedrock_runtime = BedrockRuntimeService(settings=settings)
model_runtime = ModelRuntimeService(settings=settings)
checkout_service = CheckoutService(settings=settings)
openai_realtime_service = OpenAIRealtimeService(settings=settings)
voice_registry = VoiceRegistryService(settings=settings)
elevenlabs_speech_service = ElevenLabsSpeechService(settings=settings, voice_registry=voice_registry)
speechmatics_speech_service = SpeechmaticsSpeechService(settings=settings, voice_registry=voice_registry)


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


def _speech_audio_response(audio) -> Response:
    return Response(
        content=audio.content,
        media_type=audio.media_type,
        headers={
            "Content-Disposition": f'inline; filename="{audio.filename}"',
            "X-SceneVerse-Speech-Character": audio.character,
            "X-SceneVerse-Speech-Provider": audio.provider,
            "X-SceneVerse-Speech-Model": audio.model_id,
            "X-SceneVerse-Speech-Format": audio.output_format,
        },
    )


def _is_elevenlabs_character(character: str) -> bool:
    return voice_registry.provider_for(character) == "elevenlabs"


def _normalize_speech_character(character: str) -> str:
    entry = voice_registry.resolve(character)
    if entry is not None:
        return entry.character
    normalized = character.strip().lower()
    if normalized == "darth vader":
        return "vader"
    return normalized


def _synthesize_speech(character: str, text: str | None) -> Response:
    if _is_elevenlabs_character(character):
        normalized_character = _normalize_speech_character(character)
        if text is None:
            return _speech_audio_response(elevenlabs_speech_service.synthesize_predefined(normalized_character))
        return _speech_audio_response(
            elevenlabs_speech_service.synthesize(character=normalized_character, text=text)
        )

    if text is None:
        predefined = voice_registry.predefined_text_for(character)
        if predefined:
            return _speech_audio_response(speechmatics_speech_service.synthesize_predefined(character))
        raise ValueError("Custom character speech requires text")

    return _speech_audio_response(speechmatics_speech_service.synthesize(character=character, text=text))


def _speechmatics_error_response(exc: Exception) -> HTTPException:
    if isinstance(exc, SpeechmaticsConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, SpeechmaticsSpeechError):
        return HTTPException(status_code=exc.status_code, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@app.get("/api/speech/characters", response_model=SpeechCharacterListResponse)
def list_speech_characters() -> SpeechCharacterListResponse:
    speechmatics_ready = bool(settings.speechmatics_api_key)
    elevenlabs_ready = bool(settings.elevenlabs_api_key)
    presets = []
    for entry in voice_registry.list_preset_characters():
        provider_ready = elevenlabs_ready if entry.provider == "elevenlabs" else speechmatics_ready
        presets.append(
            SpeechCharacterPreset(
                character=entry.character,
                label=entry.label,
                predefinedText=entry.predefinedText or "",
                voiceIdConfigured=bool(entry.voiceId.strip()) and provider_ready,
            )
        )
    return SpeechCharacterListResponse(
        provider="hybrid" if speechmatics_ready else "elevenlabs",
        modelId=f"{settings.elevenlabs_tts_model_id}+speechmatics-preview-tts",
        outputFormat=f"{settings.elevenlabs_output_format}|{settings.speechmatics_tts_output_format}",
        apiKeyConfigured=bool(settings.elevenlabs_api_key or settings.speechmatics_api_key),
        characters=presets,
    )


@app.get("/api/speech/test", response_class=HTMLResponse)
def speech_test_page() -> str:
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SceneVerse TTS Test</title>
    <style>
      :root {
        color-scheme: dark;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #10141d;
        color: #f3f7fb;
      }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 28px;
      }
      main {
        width: min(760px, 100%);
        display: grid;
        gap: 16px;
      }
      section {
        border: 1px solid #2e394d;
        background: #161c28;
        border-radius: 8px;
        padding: 20px;
      }
      h1 {
        margin: 0 0 8px;
        font-size: 24px;
      }
      p {
        margin: 0 0 16px;
        color: #b9c5d5;
        line-height: 1.45;
      }
      label {
        display: grid;
        gap: 8px;
        margin: 14px 0;
        color: #d7e0ec;
        font-size: 14px;
      }
      input,
      textarea {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid #3a465b;
        border-radius: 6px;
        background: #0d1119;
        color: #f3f7fb;
        padding: 10px 12px;
        font: inherit;
      }
      textarea {
        min-height: 110px;
        resize: vertical;
      }
      .row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
      }
      button {
        border: 1px solid #4f6079;
        border-radius: 6px;
        background: #253249;
        color: #ffffff;
        padding: 10px 14px;
        font: inherit;
        cursor: pointer;
      }
      button.primary {
        background: #2f6fed;
        border-color: #2f6fed;
      }
      button:disabled {
        opacity: 0.6;
        cursor: wait;
      }
      audio {
        width: 100%;
        margin-top: 14px;
      }
      code,
      output {
        display: block;
        white-space: pre-wrap;
        word-break: break-word;
        border-radius: 6px;
        background: #0d1119;
        color: #dbe7f7;
        padding: 12px;
      }
    </style>
  </head>
  <body>
    <main>
      <section>
        <h1>SceneVerse TTS Test</h1>
        <p>Maya tests Speechmatics TTS. Yoda and Vader test ElevenLabs and require an API key with text-to-speech permission.</p>
        <div class="row">
          <button type="button" data-preset="maya">Maya fallback</button>
          <button type="button" data-preset="yoda">Yoda preset</button>
          <button type="button" data-preset="vader">Vader preset</button>
        </div>
        <label>
          Character
          <input id="character" value="Maya" autocomplete="off" />
        </label>
        <label>
          Text
          <textarea id="text">We should keep moving. The scene is ready for the next shot.</textarea>
        </label>
        <div class="row">
          <button class="primary" id="synthesize" type="button">Generate speech</button>
          <button id="clear" type="button">Clear audio</button>
        </div>
        <audio id="audio" controls></audio>
      </section>
      <section>
        <p>Request</p>
        <code id="request-preview"></code>
        <p>Status</p>
        <output id="status">Ready.</output>
      </section>
    </main>
    <script>
      const character = document.querySelector("#character");
      const text = document.querySelector("#text");
      const synthesize = document.querySelector("#synthesize");
      const clear = document.querySelector("#clear");
      const audio = document.querySelector("#audio");
      const requestPreview = document.querySelector("#request-preview");
      const status = document.querySelector("#status");
      let currentUrl = null;

      const presets = {
        yoda: {
          character: "yoda",
          text: "Ready for the demo, we are. Strong with SceneVerse, this experience is."
        },
        vader: {
          character: "vader",
          text: "The scene is now under my command. Do not underestimate the power of this experience."
        },
        maya: {
          character: "Maya",
          text: "We should keep moving. The scene is ready for the next shot."
        }
      };

      function requestBody() {
        return {
          character: character.value.trim(),
          text: text.value.trim()
        };
      }

      function updatePreview() {
        requestPreview.textContent = "POST /api/speech/synthesize\\n" + JSON.stringify(requestBody(), null, 2);
      }

      function releaseAudio() {
        if (currentUrl) {
          URL.revokeObjectURL(currentUrl);
          currentUrl = null;
        }
        audio.removeAttribute("src");
      }

      async function generateSpeech() {
        releaseAudio();
        const body = requestBody();
        if (!body.character || !body.text) {
          status.textContent = "Character and text are both required.";
          return;
        }

        synthesize.disabled = true;
        status.textContent = "Calling /api/speech/synthesize...";
        try {
          const response = await fetch("/api/speech/synthesize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
          const provider = response.headers.get("x-sceneverse-speech-provider") || "unknown";
          const contentType = response.headers.get("content-type") || "unknown";
          if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
          }
          const blob = await response.blob();
          currentUrl = URL.createObjectURL(blob);
          audio.src = currentUrl;
          await audio.play().catch(() => {});
          status.textContent = `OK: ${provider}, ${contentType}, ${blob.size} bytes`;
        } catch (error) {
          status.textContent = error instanceof Error ? error.message : String(error);
        } finally {
          synthesize.disabled = false;
        }
      }

      document.querySelectorAll("[data-preset]").forEach((button) => {
        button.addEventListener("click", () => {
          const preset = presets[button.dataset.preset];
          character.value = preset.character;
          text.value = preset.text;
          updatePreview();
        });
      });
      character.addEventListener("input", updatePreview);
      text.addEventListener("input", updatePreview);
      synthesize.addEventListener("click", generateSpeech);
      clear.addEventListener("click", () => {
        releaseAudio();
        status.textContent = "Audio cleared.";
      });
      updatePreview();
    </script>
  </body>
</html>
    """


@app.post("/api/speech/predefined/{character}")
def create_predefined_speech(character: str) -> Response:
    try:
        return _synthesize_speech(character, text=None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ElevenLabsConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ElevenLabsSpeechError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (SpeechmaticsConfigurationError, SpeechmaticsSpeechError) as exc:
        raise _speechmatics_error_response(exc) from exc


@app.post("/api/speech/synthesize")
def synthesize_speech(payload: SpeechSynthesisRequest) -> Response:
    try:
        return _synthesize_speech(payload.character, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ElevenLabsConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ElevenLabsSpeechError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (SpeechmaticsConfigurationError, SpeechmaticsSpeechError) as exc:
        raise _speechmatics_error_response(exc) from exc


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
                environment=settings.environment,
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
            environment=settings.environment,
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
    try:
        return SQLiteStore(db).create_video_link(
            url=payload.url,
            source_type=payload.sourceType,
            title=payload.title,
            description=payload.description,
            thumbnail_url=payload.thumbnailUrl,
        )
    except DuplicateVideoReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Video reference already exists as {error.video_id}",
        ) from error


@app.post("/api/videos/upload", response_model=VideoAsset, status_code=status.HTTP_201_CREATED)
def upload_video(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    thumbnailUrl: str | None = Form(default=None),
    thumbnailFile: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> VideoAsset:
    video_id = f"video_{uuid4().hex[:12]}"
    storage = VideoStorageService(settings)
    stored_video = storage.store_upload(file, video_id=video_id)
    stored_thumbnail = (
        storage.store_thumbnail(thumbnailFile, video_id=video_id)
        if thumbnailFile is not None and thumbnailFile.filename
        else None
    )
    try:
        return SQLiteStore(db).create_uploaded_video(
            video_id=video_id,
            title=title,
            description=description,
            thumbnail_url=stored_thumbnail.playback_url if stored_thumbnail is not None else thumbnailUrl,
            original_filename=file.filename,
            storage_backend=stored_video.storage_backend,
            storage_key=stored_video.storage_key,
            playback_url=stored_video.playback_url,
            content_type=stored_video.content_type,
            file_size_bytes=stored_video.file_size_bytes,
        )
    except DuplicateVideoReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Video reference already exists as {error.video_id}",
        ) from error


@app.post("/api/admin/videos/{video_id}/thumbnail", response_model=VideoAsset)
def upload_admin_video_thumbnail(
    video_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoAsset:
    store = SQLiteStore(db)
    if store.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")

    stored_thumbnail = VideoStorageService(settings).store_thumbnail(file, video_id=video_id)
    video = store.update_video(video_id, {"thumbnailUrl": stored_thumbnail.playback_url})
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@app.patch("/api/admin/videos/{video_id}", response_model=VideoAsset)
def update_admin_video(video_id: str, payload: UpdateVideoRequest, db: Session = Depends(get_db)) -> VideoAsset:
    try:
        video = SQLiteStore(db).update_video(video_id, payload.model_dump(exclude_unset=True))
    except DuplicateVideoReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Video reference already exists as {error.video_id}",
        ) from error

    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@app.delete("/api/admin/videos/{video_id}", response_model=DeleteVideoResponse)
def delete_admin_video(video_id: str, db: Session = Depends(get_db)) -> DeleteVideoResponse:
    deleted = SQLiteStore(db).delete_video(video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Video not found")
    return DeleteVideoResponse(deleted=True, videoId=video_id)


@app.post("/api/admin/videos/{video_id}/download", response_model=VideoAsset)
def download_video(video_id: str, db: Session = Depends(get_db)) -> VideoAsset:
    """Download a YouTube or external video to local/S3 storage using yt-dlp."""
    import tempfile
    import shutil as _shutil
    from pathlib import Path as _Path

    store = SQLiteStore(db)
    video = store.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.playbackUrl:
        raise HTTPException(status_code=409, detail="Video already has a playback URL — download not needed")

    source_url = video.originalUrl
    if not source_url:
        raise HTTPException(status_code=422, detail="Video has no source URL to download from")

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise HTTPException(status_code=500, detail="yt-dlp is not installed on the server")

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_template = str(_Path(tmp_dir) / "%(id)s.%(ext)s")
        ydl_opts = {
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "retries": 2,
            "fragment_retries": 2,
            "socket_timeout": 30,
        }
        if settings.ytdlp_cookies_file:
            cookies_path = _Path(settings.ytdlp_cookies_file).expanduser()
            if not cookies_path.exists():
                raise HTTPException(status_code=500, detail=f"YTDLP_COOKIES_FILE does not exist: {cookies_path}")
            runtime_cookies_path = _Path(tmp_dir) / "youtube-cookies.txt"
            _shutil.copy2(str(cookies_path), str(runtime_cookies_path))
            ydl_opts["cookiefile"] = str(runtime_cookies_path)
        if settings.ytdlp_user_agent:
            ydl_opts["http_headers"] = {"User-Agent": settings.ytdlp_user_agent}
        if settings.ytdlp_pot_provider_base_url:
            ydl_opts["extractor_args"] = {
                "youtubepot-bgutilhttp": {"base_url": [settings.ytdlp_pot_provider_base_url]},
            }

        try:
            import yt_dlp as yt_dlp_mod
            with yt_dlp_mod.YoutubeDL(ydl_opts) as ydl:
                ydl.download([source_url])
        except Exception as exc:
            error_text = str(exc)
            if "Sign in to confirm" in error_text or "not a bot" in error_text or "cookies" in error_text:
                raise HTTPException(
                    status_code=424,
                    detail=(
                        "YouTube blocked anonymous server download, so SceneVerse cannot capture frames yet. "
                        "Configure YTDLP_COOKIES_FILE with exported YouTube cookies, upload a source video, "
                        f"or use a direct MP4 source. yt-dlp said: {error_text}"
                    ),
                ) from exc
            if "HTTP Error 403" in error_text:
                raise HTTPException(
                    status_code=424,
                    detail=(
                        "YouTube rejected the media URL with HTTP 403. Configure a working PO-token provider "
                        "through YTDLP_POT_PROVIDER_BASE_URL, refresh YouTube cookies, upload a source video, "
                        f"or use a direct MP4 source. yt-dlp said: {error_text}"
                    ),
                ) from exc
            raise HTTPException(status_code=502, detail=f"yt-dlp download failed: {error_text}") from exc

        downloaded_files = list(_Path(tmp_dir).glob("*.mp4"))
        if not downloaded_files:
            downloaded_files = list(_Path(tmp_dir).iterdir())
        if not downloaded_files:
            raise HTTPException(status_code=502, detail="yt-dlp produced no output file")

        downloaded_path = downloaded_files[0]
        suffix = downloaded_path.suffix.lower() or ".mp4"
        file_size = downloaded_path.stat().st_size

        storage_svc = VideoStorageService(settings)
        storage_key = storage_svc._build_storage_key(video_id=video_id, suffix=suffix)
        content_type = storage_svc._content_type_for_suffix(suffix)

        if settings.media_storage_backend == "s3":
            bucket = settings.s3_video_bucket
            if not bucket:
                raise HTTPException(status_code=500, detail="S3_VIDEO_BUCKET not configured")
            import boto3 as _boto3
            s3 = _boto3.client("s3", region_name=settings.aws_region)
            try:
                s3.upload_file(str(downloaded_path), bucket, storage_key, ExtraArgs={"ContentType": content_type})
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"S3 upload failed: {exc}") from exc
            playback_url = storage_svc._s3_playback_url(storage_key)
            storage_backend = "s3"
        else:
            target = _Path(settings.media_local_dir) / storage_key
            target.parent.mkdir(parents=True, exist_ok=True)
            _shutil.copy2(str(downloaded_path), str(target))
            playback_url = storage_svc._local_playback_url(storage_key)
            storage_backend = "local"

    updated = store.update_video(video_id, {
        "playbackUrl": playback_url,
        "storageBackend": storage_backend,
        "storageKey": storage_key,
        "contentType": content_type,
        "fileSizeBytes": file_size,
        "status": "ready",
    })
    if updated is None:
        raise HTTPException(status_code=404, detail="Video not found after download")
    return updated


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


@app.post("/api/character/router", response_model=CharacterRouterResponse)
def route_character(payload: CharacterRouterRequest, db: Session = Depends(get_db)) -> CharacterRouterResponse:
    scene = SQLiteStore(db).get_scene(payload.sceneId)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        return character_router.route(scene=scene, message=payload.message, target_agent_id=payload.targetAgentId)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/character/chat", response_model=ChatResponse)
def character_chat(payload: CharacterChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    store = SQLiteStore(db)
    scene = store.get_scene(payload.sceneId)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    try:
        route = character_router.route(scene=scene, message=payload.message, target_agent_id=payload.characterId)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    character = _find_character(scene, route.targetAgent.id)
    response_text = orchestrator.character_agent.respond(scene, character, payload.message, scene.memorySummary)
    response_text = orchestrator.director_agent.validate_character_response(response_text)
    responding_agent = route.targetAgent
    updated_summary = orchestrator.memory_agent.update_summary(scene.memorySummary, payload.message, responding_agent.name)
    agent_trace = [
        *route.agentTrace,
        AgentTraceStep(step="respond_in_character", agent=character.name, status="complete"),
        AgentTraceStep(step="validate_consistency", agent="director", status="complete"),
        AgentTraceStep(step="update_memory", agent="memory", status="complete"),
    ]
    response = ChatResponse(
        respondingAgent=responding_agent,
        response=response_text,
        updatedMemorySummary=updated_summary,
        agentTrace=agent_trace,
    )
    store.save_turn(payload.sceneId, payload.message, response)
    store.update_memory_summary(payload.sceneId, updated_summary)
    return response


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

    event_type = event["type"] if isinstance(event, dict) else getattr(event, "type", "unknown")
    return {"received": True, "eventType": event_type}
