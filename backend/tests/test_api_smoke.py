from fastapi.testclient import TestClient

from app.main import app


def test_scene_chat_research_checkout_flow():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

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

        research = client.post(
            "/api/research",
            json={"sceneId": scene["sceneId"], "query": "What genre references does this scene evoke?"},
        )
        assert research.status_code == 200
        assert research.json()["sources"][0]["title"] == "Exa integration placeholder"

        checkout = client.post(
            "/api/checkout",
            json={"sceneId": scene["sceneId"], "unlockType": "premium_scene"},
        )
        assert checkout.status_code == 200
        assert checkout.json()["mode"] == "simulated"
