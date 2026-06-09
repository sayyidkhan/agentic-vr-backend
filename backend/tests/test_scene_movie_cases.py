from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


TESTS_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = TESTS_DIR / "fixtures"
MANIFEST_PATH = FIXTURE_DIR / "movie_scene_cases.json"
IMAGE_DIR = FIXTURE_DIR / "movie_images"
FALLBACK_SCENE_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "fallback_scene.json"
FALLBACK_SCENE = json.loads(FALLBACK_SCENE_PATH.read_text(encoding="utf-8"))
CASES = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def image_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    resolved_mime = mime_type or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{resolved_mime};base64,{encoded}"


@pytest.mark.parametrize("case", CASES, ids=[case["slug"] for case in CASES])
def test_movie_fixture_analyze_requests_currently_use_fallback_scene(case: dict) -> None:
    image_path = IMAGE_DIR / case["fileName"]
    if not image_path.exists():
        pytest.skip(f"Missing fixture image {image_path.name}. Run backend/scripts/download_movie_scene_fixtures.py first.")

    payload = {
        "frame": image_to_data_url(image_path),
        "timestamp": case["timestamp"],
        "transcriptSegment": case["transcriptSegment"],
        "videoMetadata": case["videoMetadata"],
    }

    with TestClient(app) as client:
        response = client.post("/api/scenes/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()

    assert body["scene"]["videoId"] == case["videoMetadata"]["videoId"]
    assert body["scene"]["timestamp"] == case["timestamp"]
    assert body["scene"]["frameRef"] == "inline-frame"
    assert body["scene"]["transcriptSegment"] == case["transcriptSegment"]

    assert body["agentTrace"][0]["step"] == "receive_frame"
    assert body["agentTrace"][0]["status"] == "complete"
    assert body["agentTrace"][1]["step"] == "parse_scene"
    assert body["agentTrace"][1]["status"] == "fallback"
    assert body["agentTrace"][2]["step"] == "initialize_memory"
    assert body["agentTrace"][2]["status"] == "complete"

    assert body["scene"]["setting"] == FALLBACK_SCENE["setting"]
    assert body["scene"]["emotionalTone"] == FALLBACK_SCENE["emotionalTone"]
    assert body["scene"]["conflict"] == FALLBACK_SCENE["conflict"]
    assert body["directorContext"] == FALLBACK_SCENE["directorContext"]
    assert [character["name"] for character in body["characters"]] == [item["name"] for item in FALLBACK_SCENE["characters"]]
    assert case["transcriptSegment"] in body["sceneSummary"]
