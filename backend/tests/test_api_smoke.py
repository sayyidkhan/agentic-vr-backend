from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from types import SimpleNamespace
import uuid

from botocore.exceptions import NoCredentialsError
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import app.main as app_main

from app.config import Settings
from app.main import app
from app.models.schemas import (
    AgentTraceStep,
    AnalyzeSceneResponse,
    Character,
    ResearchResponse,
    ResearchSource,
    Scene,
    SpeechCharacterPreset,
)
from app.services.video_storage import VideoStorageService


def test_sceneverse_profile_pairs_database_and_media_storage():
    local_settings = Settings(
        _env_file=None,
        sceneverse_profile="local",
        local_database_url="sqlite:///./data/local-test.db",
        local_media_local_dir="./data/local-media-test",
        cloud_s3_video_bucket="should-not-be-used",
    )
    assert local_settings.environment == "local"
    assert local_settings.database_url == "sqlite:///./data/local-test.db"
    assert local_settings.media_storage_backend == "local"
    assert local_settings.media_local_dir == "./data/local-media-test"
    assert local_settings.s3_video_bucket is None

    cloud_settings = Settings(
        _env_file=None,
        sceneverse_profile="cloud",
        cloud_database_url="sqlite:////ecs/sceneverse.db",
        cloud_s3_video_bucket="sceneverse-dev-videos",
        cloud_media_cdn_base_url="https://cdn.example.com",
    )
    assert cloud_settings.environment == "cloud"
    assert cloud_settings.database_url == "sqlite:////ecs/sceneverse.db"
    assert cloud_settings.media_storage_backend == "s3"
    assert cloud_settings.s3_video_bucket == "sceneverse-dev-videos"
    assert cloud_settings.media_cdn_base_url == "https://cdn.example.com"

    speech_settings = Settings(
        _env_file=None,
        elevenlabs_api_key="test-key",
        elevenlabs_yoda_voice_id="voice-yoda",
        elevenlabs_vader_voice_id="voice-vader",
        speechmatics_api_key="speechmatics-key",
    )
    assert speech_settings.elevenlabs_api_key == "test-key"
    assert speech_settings.elevenlabs_tts_model_id == "eleven_multilingual_v2"
    assert speech_settings.elevenlabs_output_format == "mp3_44100_128"
    assert speech_settings.elevenlabs_yoda_voice_id == "voice-yoda"
    assert speech_settings.elevenlabs_vader_voice_id == "voice-vader"
    assert speech_settings.speechmatics_api_key == "speechmatics-key"
    assert speech_settings.speechmatics_tts_output_format == "wav_16000"
    assert speech_settings.speechmatics_tts_voice_id == "jack"


def test_s3_upload_without_credentials_returns_actionable_error(monkeypatch):
    class StubS3Client:
        def upload_fileobj(self, *args, **kwargs):
            raise NoCredentialsError()

    settings = Settings(
        _env_file=None,
        sceneverse_profile="cloud",
        cloud_s3_video_bucket="sceneverse-dev-videos",
        cloud_media_cdn_base_url="https://cdn.example.com",
    )
    monkeypatch.setattr("app.services.video_storage.boto3.client", lambda *args, **kwargs: StubS3Client())
    upload = SimpleNamespace(filename="demo.mp4", content_type="video/mp4", file=BytesIO(b"0" * 2048))

    with pytest.raises(HTTPException) as error:
        VideoStorageService(settings).store_upload(upload, video_id="video_test")

    assert error.value.status_code == 500
    assert "AWS credentials are not available" in error.value.detail


def test_s3_upload_refreshes_expiring_cli_login_credentials(monkeypatch):
    captured_client_kwargs = {}

    class StubS3Client:
        def upload_fileobj(self, *args, **kwargs):
            return None

    def stub_client(*args, **kwargs):
        captured_client_kwargs.update(kwargs)
        return StubS3Client()

    def stub_run(*args, **kwargs):
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "Version": 1,
                    "AccessKeyId": "AKIA_TEST",
                    "SecretAccessKey": "SECRET_TEST",
                    "SessionToken": "TOKEN_TEST",
                    "Expiration": "2026-06-10T06:00:00+00:00",
                }
            )
        )

    settings = Settings(
        _env_file=None,
        sceneverse_profile="cloud",
        cloud_s3_video_bucket="sceneverse-dev-videos",
        cloud_media_cdn_base_url="https://cdn.example.com",
    )
    monkeypatch.setenv("AWS_PROFILE", "sceneverse")
    monkeypatch.setenv(
        "AWS_CREDENTIAL_EXPIRATION",
        (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
    )
    monkeypatch.setattr("app.services.video_storage.subprocess.run", stub_run)
    monkeypatch.setattr("app.services.video_storage.boto3.client", stub_client)
    upload = SimpleNamespace(filename="demo.mp4", content_type="video/mp4", file=BytesIO(b"0" * 2048))

    stored = VideoStorageService(settings).store_upload(upload, video_id="video_test")

    assert stored.storage_backend == "s3"
    assert captured_client_kwargs["aws_access_key_id"] == "AKIA_TEST"
    assert captured_client_kwargs["aws_secret_access_key"] == "SECRET_TEST"
    assert captured_client_kwargs["aws_session_token"] == "TOKEN_TEST"


def test_scene_chat_research_checkout_flow():
    original_bedrock_runtime = app_main.bedrock_runtime
    original_model_runtime = app_main.model_runtime
    original_research_agent = app_main.research_agent
    original_scene_parser = app_main.scene_parser
    original_checkout_service = app_main.checkout_service
    original_openai_realtime_service = app_main.openai_realtime_service
    original_elevenlabs_speech_service = app_main.elevenlabs_speech_service
    original_speechmatics_speech_service = app_main.speechmatics_speech_service
    original_orchestrator_research_agent = app_main.orchestrator.research_agent
    original_media_storage_backend = app_main.settings.media_storage_backend
    original_elevenlabs_api_key = app_main.settings.elevenlabs_api_key
    original_speechmatics_api_key = app_main.settings.speechmatics_api_key

    class StubBedrockRuntime:
        def probe(self, prompt: str):
            return app_main.BedrockProbeResponse(
                status="ok",
                provider="amazon",
                modelId="amazon.nova-lite-v1:0",
                region="us-east-1",
                prompt=prompt,
                outputText="BEDROCK_OK ready",
            )

    class StubModelRuntime:
        def list_models(self):
            return app_main.ModelCatalogResponse(
                defaultModelKey="claude_sonnet_4_6",
                models=[
                    app_main.EnabledModelResponse(
                        key="claude_sonnet_4_6",
                        label="Claude Sonnet 4.6",
                        provider="anthropic",
                        transport="bedrock",
                        modelId="global.anthropic.claude-sonnet-4-6",
                        region="us-east-1",
                        enabled=True,
                        credentialSource="AWS_BEARER_TOKEN_BEDROCK",
                        credentialConfigured=True,
                    ),
                    app_main.EnabledModelResponse(
                        key="claude_haiku_4_5",
                        label="Claude Haiku 4.5",
                        provider="anthropic",
                        transport="bedrock",
                        modelId="global.anthropic.claude-haiku-4-5-20251001-v1:0",
                        region="us-east-1",
                        enabled=True,
                        credentialSource="AWS_BEARER_TOKEN_BEDROCK",
                        credentialConfigured=True,
                    ),
                    app_main.EnabledModelResponse(
                        key="kimi_k2_5",
                        label="Kimi K2.5",
                        provider="moonshotai",
                        transport="bedrock",
                        modelId="moonshotai.kimi-k2.5",
                        region="us-east-1",
                        enabled=True,
                        credentialSource="AWS_BEARER_TOKEN_BEDROCK",
                        credentialConfigured=True,
                    ),
                ],
            )

        def probe(self, prompt: str, model_key: str | None = None):
            chosen_key = model_key or "claude_sonnet_4_6"
            chosen_provider = "anthropic" if chosen_key in {"claude_sonnet_4_6", "claude_haiku_4_5"} else "moonshotai"
            chosen_transport = "bedrock"
            chosen_model_id = {
                "claude_sonnet_4_6": "global.anthropic.claude-sonnet-4-6",
                "claude_haiku_4_5": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                "kimi_k2_5": "moonshotai.kimi-k2.5",
            }[chosen_key]
            chosen_label = {
                "claude_sonnet_4_6": "Claude Sonnet 4.6",
                "claude_haiku_4_5": "Claude Haiku 4.5",
                "kimi_k2_5": "Kimi K2.5",
            }[chosen_key]
            return app_main.ModelProbeResponse(
                status="ok",
                modelKey=chosen_key,
                label=chosen_label,
                provider=chosen_provider,
                transport=chosen_transport,
                modelId=chosen_model_id,
                region="us-east-1",
                prompt=prompt,
                outputText=f"{chosen_key} ready",
            )

        def probe_all(self, prompt: str):
            return app_main.ModelProbeBatchResponse(
                status="ok",
                prompt=prompt,
                results=[
                    self.probe(prompt=prompt, model_key="claude_sonnet_4_6"),
                    self.probe(prompt=prompt, model_key="claude_haiku_4_5"),
                    self.probe(prompt=prompt, model_key="kimi_k2_5"),
                ],
            )

    class StubResearchAgent:
        def search(self, query: str):
            return ResearchResponse(
                summary=f"Stub research summary for query: {query}",
                sources=[
                    ResearchSource(
                        title="Exa integration placeholder",
                        url="https://exa.ai",
                        snippet="Fallback source returned until EXA_API_KEY is configured.",
                    )
                ],
                recommendedContext=f"Use external context only in Director Agent responses for query: {query}",
            )

    class StubCheckoutService:
        def create_checkout(self, payload):
            return app_main.CheckoutResponse(
                checkoutUrl=f"{app_main.settings.frontend_url}/unlock/simulated?sceneId={payload.sceneId}",
                mode="simulated",
            )

    class StubElevenLabsSpeechService:
        def list_character_presets(self):
            return [
                SpeechCharacterPreset(
                    character="yoda",
                    label="Yoda",
                    predefinedText="Ready for the demo, we are.",
                    voiceIdConfigured=True,
                ),
                SpeechCharacterPreset(
                    character="vader",
                    label="Darth Vader",
                    predefinedText="The scene is now under my command.",
                    voiceIdConfigured=True,
                ),
            ]

        def synthesize_predefined(self, character):
            return self.synthesize(character=character, text=f"{character} predefined")

        def synthesize(self, character, text):
            return SimpleNamespace(
                character=character,
                provider="elevenlabs",
                voice_id=f"voice-{character}",
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                text=text,
                content=f"{character}:{text}".encode("utf-8"),
                media_type="audio/mpeg",
                filename=f"sceneverse-{character}.mp3",
            )

    class StubSpeechmaticsSpeechService:
        def synthesize(self, character, text):
            normalized_character = character.strip().lower().replace(" ", "_")
            return SimpleNamespace(
                character=normalized_character,
                provider="speechmatics",
                voice_id="jack",
                model_id="speechmatics-preview-tts",
                output_format="wav_16000",
                text=text,
                content=f"{normalized_character}:{text}".encode("utf-8"),
                media_type="audio/wav",
                filename=f"sceneverse-{normalized_character}.wav",
            )

    class StubSceneParser:
        def analyze(self, payload):
            scene_id = f"scene_stub_{uuid.uuid4().hex[:8]}"
            scene = Scene(
                sceneId=scene_id,
                videoId=payload.videoMetadata.videoId or "demo-clip",
                timestamp=payload.timestamp,
                frameRef="inline-frame" if payload.frame else None,
                transcriptSegment=payload.transcriptSegment,
                summary="A tense cinematic standoff unfolds after the characters realize their supposed refuge may be compromised. Transcript context: You said this place was safe.",
                setting="A dim transit concourse after closing hours",
                emotionalTone="tense, suspicious, and urgent",
                conflict="One character wants to keep moving while another needs the truth before trusting the plan",
                objects=["flickering departure board", "abandoned suitcase", "security camera", "rain-streaked glass"],
                characters=[
                    Character(
                        characterId=f"{scene_id}_maya",
                        sceneId=scene_id,
                        name="Maya",
                        role="The cautious survivor who notices the trap first",
                        personality="observant, guarded, direct",
                        emotionalState="tense but controlled",
                        goals=["protect the group", "force the truth into the open"],
                        knowledgeBoundaries=["Maya does not know who is controlling the station cameras."],
                        speakingStyle="short, precise, suspicious",
                    ),
                    Character(
                        characterId=f"{scene_id}_ren",
                        sceneId=scene_id,
                        name="Ren",
                        role="The conflicted guide who may be hiding a prior deal",
                        personality="resourceful, evasive, loyal under pressure",
                        emotionalState="anxious and defensive",
                        goals=["get everyone out before midnight", "avoid revealing the full bargain"],
                        knowledgeBoundaries=["Ren knows the route but not the full identity of the watcher."],
                        speakingStyle="measured, indirect, occasionally sharp",
                    ),
                ],
                directorContext="The scene uses an empty public space to make the characters feel exposed despite being physically alone.",
                memorySummary="Scene initialized at 42.50s. Known characters: Maya, Ren. Core tension: One character wants to keep moving while another needs the truth before trusting the plan.",
                analysisMode="fallback",
            )
            return AnalyzeSceneResponse(
                sceneId=scene.sceneId,
                sceneSummary=scene.summary,
                scene=scene,
                characters=scene.characters,
                directorContext=scene.directorContext,
                memorySummary=scene.memorySummary,
                agentTrace=[
                    AgentTraceStep(step="receive_frame", agent="api", status="complete"),
                    AgentTraceStep(step="parse_scene", agent="scene_parser", status="fallback"),
                    AgentTraceStep(step="initialize_memory", agent="memory", status="complete"),
                ],
                analysisMode="fallback",
                sourceModelId=None,
            )

    try:
        app_main.bedrock_runtime = StubBedrockRuntime()
        app_main.model_runtime = StubModelRuntime()
        app_main.research_agent = StubResearchAgent()
        app_main.scene_parser = StubSceneParser()
        app_main.checkout_service = StubCheckoutService()
        app_main.elevenlabs_speech_service = StubElevenLabsSpeechService()
        app_main.speechmatics_speech_service = StubSpeechmaticsSpeechService()
        app_main.orchestrator.research_agent = StubResearchAgent()
        app_main.settings.media_storage_backend = "local"
        app_main.settings.elevenlabs_api_key = "test-key"
        app_main.settings.speechmatics_api_key = "speechmatics-key"

        with TestClient(app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            speech_test_page = client.get("/api/speech/test")
            assert speech_test_page.status_code == 200
            assert "SceneVerse TTS Test" in speech_test_page.text

            bedrock_probe = client.post("/api/bedrock/test", json={})
            assert bedrock_probe.status_code == 200
            assert bedrock_probe.json()["status"] == "ok"
            assert bedrock_probe.json()["provider"] == "amazon"
            assert "BEDROCK_OK" in bedrock_probe.json()["outputText"]

            model_catalog = client.get("/api/models")
            assert model_catalog.status_code == 200
            assert model_catalog.json()["defaultModelKey"] == "claude_sonnet_4_6"
            assert len(model_catalog.json()["models"]) == 3

            model_probe = client.post("/api/models/test", json={"modelKey": "claude_haiku_4_5"})
            assert model_probe.status_code == 200
            assert model_probe.json()["provider"] == "anthropic"
            assert model_probe.json()["transport"] == "bedrock"

            model_probe_all = client.post("/api/models/test-all", json={})
            assert model_probe_all.status_code == 200
            assert model_probe_all.json()["status"] == "ok"
            assert len(model_probe_all.json()["results"]) == 3

            speech_characters = client.get("/api/speech/characters")
            assert speech_characters.status_code == 200
            assert speech_characters.json()["provider"] == "hybrid"
            assert speech_characters.json()["apiKeyConfigured"] is True
            assert speech_characters.json()["characters"][0]["character"] == "yoda"

            yoda_speech = client.post("/api/speech/predefined/yoda")
            assert yoda_speech.status_code == 200
            assert yoda_speech.headers["content-type"] == "audio/mpeg"
            assert yoda_speech.headers["x-sceneverse-speech-character"] == "yoda"
            assert yoda_speech.content == b"yoda:yoda predefined"

            vader_speech = client.post(
                "/api/speech/synthesize",
                json={"character": "vader", "text": "You do not know the power of the demo."},
            )
            assert vader_speech.status_code == 200
            assert vader_speech.headers["x-sceneverse-speech-character"] == "vader"
            assert vader_speech.headers["x-sceneverse-speech-provider"] == "elevenlabs"
            assert vader_speech.content == b"vader:You do not know the power of the demo."

            custom_character_speech = client.post(
                "/api/speech/synthesize",
                json={"character": "Maya", "text": "We should keep moving."},
            )
            assert custom_character_speech.status_code == 200
            assert custom_character_speech.headers["content-type"] == "audio/wav"
            assert custom_character_speech.headers["x-sceneverse-speech-character"] == "maya"
            assert custom_character_speech.headers["x-sceneverse-speech-provider"] == "speechmatics"
            assert custom_character_speech.content == b"maya:We should keep moving."

            db_health = client.get("/health/db")
            assert db_health.status_code == 200
            assert db_health.json()["status"] == "ok"
            assert db_health.json()["database"] == "sqlite"
            assert db_health.json()["quickCheck"] == "ok"

            empty_scenes = client.get("/api/db/scenes")
            assert empty_scenes.status_code == 200
            assert empty_scenes.json()["table"] == "scenes"
            initial_scene_count = empty_scenes.json()["rowCount"]

            empty_videos = client.get("/api/videos")
            assert empty_videos.status_code == 200
            initial_video_count = empty_videos.json()["rowCount"]

            linked_video = client.post(
                "/api/videos/link",
                json={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "title": "Reference Clip",
                    "description": "Reference material for admin preview.",
                    "thumbnailUrl": "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
                    "sourceType": "youtube",
                },
            )
            assert linked_video.status_code == 201
            linked_video_data = linked_video.json()
            assert linked_video_data["sourceType"] == "youtube"
            assert linked_video_data["description"] == "Reference material for admin preview."
            assert linked_video_data["thumbnailUrl"] == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
            assert linked_video_data["originalUrl"].startswith("https://www.youtube.com/")

            duplicate_linked_video = client.post(
                "/api/videos/link",
                json={
                    "url": "https://youtu.be/dQw4w9WgXcQ",
                    "title": "Duplicate Reference Clip",
                    "sourceType": "youtube",
                },
            )
            assert duplicate_linked_video.status_code == 409
            assert linked_video_data["videoId"] in duplicate_linked_video.json()["detail"]

            linked_thumbnail_upload = client.post(
                f"/api/admin/videos/{linked_video_data['videoId']}/thumbnail",
                files={"file": ("reference-poster.png", BytesIO(b"fake-png-thumbnail"), "image/png")},
            )
            assert linked_thumbnail_upload.status_code == 200
            linked_thumbnail_data = linked_thumbnail_upload.json()
            assert linked_thumbnail_data["thumbnailUrl"].endswith(
                f"/videos/thumbnails/{linked_video_data['videoId']}.png"
            )

            uploaded_video = client.post(
                "/api/videos/upload",
                data={
                    "title": "Uploaded Demo Clip",
                    "description": "Uploaded local media for QA.",
                    "thumbnailUrl": "https://cdn.example.com/thumbs/uploaded-demo.jpg",
                },
                files={
                    "file": ("demo.mp4", BytesIO(b"0" * 2048), "video/mp4"),
                    "thumbnailFile": ("uploaded-poster.webp", BytesIO(b"fake-webp-thumbnail"), "image/webp"),
                },
            )
            assert uploaded_video.status_code == 201
            uploaded_video_data = uploaded_video.json()
            assert uploaded_video_data["sourceType"] == "upload"
            assert uploaded_video_data["description"] == "Uploaded local media for QA."
            assert uploaded_video_data["thumbnailUrl"].endswith(
                f"/videos/thumbnails/{uploaded_video_data['videoId']}.webp"
            )
            assert uploaded_video_data["storageBackend"] == app_main.settings.media_storage_backend
            assert uploaded_video_data["playbackUrl"]

            video_list = client.get("/api/videos", params={"limit": 10})
            assert video_list.status_code == 200
            assert video_list.json()["rowCount"] >= initial_video_count + 2
            assert video_list.json()["items"][0]["videoId"]

            fetched_video = client.get(f"/api/videos/{uploaded_video_data['videoId']}")
            assert fetched_video.status_code == 200
            assert fetched_video.json()["title"] == "Uploaded Demo Clip"

            updated_video = client.patch(
                f"/api/admin/videos/{uploaded_video_data['videoId']}",
                json={
                    "title": "Updated Demo Clip",
                    "description": "Updated catalogue description.",
                    "thumbnailUrl": "https://cdn.example.com/thumbs/updated-demo.jpg",
                    "status": "draft",
                },
            )
            assert updated_video.status_code == 200
            assert updated_video.json()["title"] == "Updated Demo Clip"
            assert updated_video.json()["description"] == "Updated catalogue description."
            assert updated_video.json()["thumbnailUrl"] == "https://cdn.example.com/thumbs/updated-demo.jpg"
            assert updated_video.json()["status"] == "draft"

            video_rows = client.get("/api/db/videos", params={"limit": 2})
            assert video_rows.status_code == 200
            assert video_rows.json()["rowCount"] >= initial_video_count + 2

            deleted_video = client.delete(f"/api/admin/videos/{linked_video_data['videoId']}")
            assert deleted_video.status_code == 200
            assert deleted_video.json() == {"deleted": True, "videoId": linked_video_data["videoId"]}

            deleted_video_lookup = client.get(f"/api/videos/{linked_video_data['videoId']}")
            assert deleted_video_lookup.status_code == 404

            analyze = client.post(
                "/api/scenes/analyze",
                json={
                    "frame": "data:image/jpeg;base64,demo",
                    "timestamp": 42.5,
                    "transcriptSegment": "You said this place was safe.",
                    "videoMetadata": {"videoId": "demo-clip", "title": "Demo Clip"},
                },
            )
            assert analyze.status_code == 200
            scene = analyze.json()
            assert len(scene["characters"]) >= 2
            assert scene["agentTrace"][1]["status"] == "fallback"
            assert scene["analysisMode"] == "fallback"

            character_session = client.post(
                "/api/character/new",
                json={"sceneId": scene["sceneId"], "characterId": scene["characters"][0]["characterId"]},
            )
            assert character_session.status_code == 200
            character_session_data = character_session.json()
            assert character_session_data["sceneId"] == scene["sceneId"]
            assert character_session_data["character"]["characterId"] == scene["characters"][0]["characterId"]
            assert character_session_data["characterSessionId"].startswith("character_session_")

            character_route = client.post(
                "/api/character/router",
                json={
                    "sceneId": scene["sceneId"],
                    "message": "I want to ask Ren why he is hiding the route.",
                },
            )
            assert character_route.status_code == 200
            character_route_data = character_route.json()
            assert character_route_data["targetAgent"]["name"] == "Ren"
            assert character_route_data["targetAgent"]["type"] == "character"
            assert character_route_data["confidence"] > 0

            character_chat = client.post(
                "/api/character/chat",
                json={
                    "sceneId": scene["sceneId"],
                    "message": "Ren, what are you not telling us about the route?",
                },
            )
            assert character_chat.status_code == 200
            character_chat_data = character_chat.json()
            assert character_chat_data["respondingAgent"]["name"] == "Ren"
            assert character_chat_data["respondingAgent"]["type"] == "character"
            assert character_chat_data["response"]

            scene_rows = client.get("/api/db/scenes", params={"limit": 10})
            assert scene_rows.status_code == 200
            assert scene_rows.json()["rowCount"] >= initial_scene_count + 1
            assert any(row["scene_id"] == scene["sceneId"] for row in scene_rows.json()["rows"])

            character_session_rows = client.get("/api/db/character_sessions", params={"limit": 10})
            assert character_session_rows.status_code == 200
            assert character_session_rows.json()["rowCount"] >= 1
            assert any(row["scene_id"] == scene["sceneId"] for row in character_session_rows.json()["rows"])

            chat = client.post(
                "/api/chat",
                json={
                    "sceneId": scene["sceneId"],
                    "message": "What are you feeling right now?",
                    "targetAgentId": scene["characters"][0]["characterId"],
                },
            )
            assert chat.status_code == 200
            assert chat.json()["respondingAgent"]["type"] == "character"

            turn_rows = client.get("/api/db/conversation_turns", params={"limit": 10})
            assert turn_rows.status_code == 200
            assert turn_rows.json()["rowCount"] >= 1
            assert any(row["scene_id"] == scene["sceneId"] for row in turn_rows.json()["rows"])

            research = client.post(
                "/api/research",
                json={"sceneId": scene["sceneId"], "query": "What genre references does this scene evoke?"},
            )
            assert research.status_code == 200
            assert research.json()["sources"][0]["title"] == "Exa integration placeholder"

            research_rows = client.get("/api/db/research_contexts", params={"limit": 10})
            assert research_rows.status_code == 200
            assert research_rows.json()["rowCount"] >= 1
            assert any(row["scene_id"] == scene["sceneId"] for row in research_rows.json()["rows"])

            checkout = client.post(
                "/api/checkout",
                json={"sceneId": scene["sceneId"], "unlockType": "premium_scene"},
            )
            assert checkout.status_code == 200
            assert checkout.json()["mode"] == "simulated"

            missing_table = client.get("/api/db/not_a_table")
            assert missing_table.status_code == 404
    finally:
        app_main.bedrock_runtime = original_bedrock_runtime
        app_main.model_runtime = original_model_runtime
        app_main.research_agent = original_research_agent
        app_main.scene_parser = original_scene_parser
        app_main.checkout_service = original_checkout_service
        app_main.openai_realtime_service = original_openai_realtime_service
        app_main.elevenlabs_speech_service = original_elevenlabs_speech_service
        app_main.speechmatics_speech_service = original_speechmatics_speech_service
        app_main.orchestrator.research_agent = original_orchestrator_research_agent
        app_main.settings.media_storage_backend = original_media_storage_backend
        app_main.settings.elevenlabs_api_key = original_elevenlabs_api_key
        app_main.settings.speechmatics_api_key = original_speechmatics_api_key
