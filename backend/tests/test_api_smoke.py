from fastapi.testclient import TestClient
import app.main as app_main

from app.main import app


def test_scene_chat_research_checkout_flow():
    with TestClient(app) as client:
        original_bedrock_runtime = app_main.bedrock_runtime
        original_model_runtime = app_main.model_runtime

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

        app_main.bedrock_runtime = StubBedrockRuntime()
        app_main.model_runtime = StubModelRuntime()
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

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

        db_health = client.get("/health/db")
        assert db_health.status_code == 200
        assert db_health.json()["status"] == "ok"
        assert db_health.json()["database"] == "sqlite"
        assert db_health.json()["quickCheck"] == "ok"

        empty_scenes = client.get("/api/db/scenes")
        assert empty_scenes.status_code == 200
        assert empty_scenes.json()["table"] == "scenes"
        initial_scene_count = empty_scenes.json()["rowCount"]

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

        character_session = client.post(
            "/api/character/new",
            json={"sceneId": scene["sceneId"], "characterId": scene["characters"][0]["characterId"]},
        )
        assert character_session.status_code == 200
        character_session_data = character_session.json()
        assert character_session_data["sceneId"] == scene["sceneId"]
        assert character_session_data["character"]["characterId"] == scene["characters"][0]["characterId"]
        assert character_session_data["characterSessionId"].startswith("character_session_")

        scene_rows = client.get("/api/db/scenes", params={"limit": 1})
        assert scene_rows.status_code == 200
        assert scene_rows.json()["rowCount"] >= initial_scene_count + 1
        assert scene_rows.json()["rows"][0]["scene_id"] == scene["sceneId"]

        character_session_rows = client.get("/api/db/character_sessions", params={"limit": 1})
        assert character_session_rows.status_code == 200
        assert character_session_rows.json()["rowCount"] >= 1
        assert character_session_rows.json()["rows"][0]["scene_id"] == scene["sceneId"]

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

        turn_rows = client.get("/api/db/conversation_turns", params={"limit": 1})
        assert turn_rows.status_code == 200
        assert turn_rows.json()["rowCount"] >= 1
        assert turn_rows.json()["rows"][0]["scene_id"] == scene["sceneId"]

        research = client.post(
            "/api/research",
            json={"sceneId": scene["sceneId"], "query": "What genre references does this scene evoke?"},
        )
        assert research.status_code == 200
        assert research.json()["sources"][0]["title"] == "Exa integration placeholder"

        research_rows = client.get("/api/db/research_contexts", params={"limit": 1})
        assert research_rows.status_code == 200
        assert research_rows.json()["rowCount"] >= 1
        assert research_rows.json()["rows"][0]["scene_id"] == scene["sceneId"]

        checkout = client.post(
            "/api/checkout",
            json={"sceneId": scene["sceneId"], "unlockType": "premium_scene"},
        )
        assert checkout.status_code == 200
        assert checkout.json()["mode"] == "simulated"

        missing_table = client.get("/api/db/not_a_table")
        assert missing_table.status_code == 404
        app_main.bedrock_runtime = original_bedrock_runtime
        app_main.model_runtime = original_model_runtime
