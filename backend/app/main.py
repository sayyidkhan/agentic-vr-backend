from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.agents.orchestrator import OrchestratorAgent
from app.agents.scene_parser import SceneParserAgent
from app.config import get_settings
from app.database import get_db, init_db
from app.models.schemas import (
    AnalyzeSceneRequest,
    AnalyzeSceneResponse,
    ChatRequest,
    ChatResponse,
    CheckoutRequest,
    CheckoutResponse,
    HealthResponse,
    ResearchRequest,
    ResearchResponse,
)
from app.services.checkout import CheckoutService
from app.store.sqlite_store import SQLiteStore

settings = get_settings()


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

scene_parser = SceneParserAgent()
orchestrator = OrchestratorAgent()
checkout_service = CheckoutService(settings=settings)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.environment)


@app.post("/api/scenes/analyze", response_model=AnalyzeSceneResponse)
def analyze_scene(payload: AnalyzeSceneRequest, db: Session = Depends(get_db)) -> AnalyzeSceneResponse:
    result = scene_parser.analyze(payload)
    SQLiteStore(db).save_scene(result.scene)
    return result


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

    result = orchestrator.research_agent.search(payload.query)
    store.save_research(payload.sceneId, payload.query, result.summary)
    return result


@app.post("/api/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)) -> CheckoutResponse:
    scene = SQLiteStore(db).get_scene(payload.sceneId)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    return checkout_service.create_checkout(payload)
