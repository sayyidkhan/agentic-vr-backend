from __future__ import annotations

import argparse
import base64
import json
import mimetypes
from pathlib import Path
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT_DIR / "tests" / "fixtures" / "movie_scene_cases.json"
IMAGE_DIR = ROOT_DIR / "tests" / "fixtures" / "movie_images"


def load_cases() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def image_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    resolved_mime = mime_type or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{resolved_mime};base64,{encoded}"


def call_analyze(base_url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/api/scenes/analyze",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the scene analysis API against the movie fixture set.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    args = parser.parse_args()

    for case in load_cases():
        image_path = IMAGE_DIR / case["fileName"]
        if not image_path.exists():
            raise FileNotFoundError(
                f"Missing fixture image: {image_path}. Run backend/scripts/download_movie_scene_fixtures.py first."
            )

        payload = {
            "frame": image_to_data_url(image_path),
            "timestamp": case["timestamp"],
            "transcriptSegment": case["transcriptSegment"],
            "videoMetadata": case["videoMetadata"],
        }
        result = call_analyze(args.base_url, payload)
        print(f"[{case['slug']}]")
        print(f"  title: {case['title']}")
        print(f"  sceneId: {result['sceneId']}")
        print(f"  analysisMode: {result.get('analysisMode')}")
        print(f"  sourceModelId: {result.get('sourceModelId')}")
        print(f"  detectedWorkTitle: {result['scene'].get('detectedWorkTitle')}")
        print(f"  detectedUniverse: {result['scene'].get('detectedUniverse')}")
        print(f"  parseStatus: {result['agentTrace'][1]['status']}")
        print(f"  summary: {result['sceneSummary']}")
        for character in result["characters"]:
            print(
                "  character:"
                f" {character['name']}"
                f" | franchise={character.get('franchise')}"
                f" | portrayedBy={character.get('portrayedBy')}"
                f" | confidence={character.get('identificationConfidence')}"
            )
            if character.get("profileSummary"):
                print(f"    profileSummary: {character['profileSummary']}")
            if character.get("profileSources"):
                print(f"    profileSources: {len(character['profileSources'])}")


if __name__ == "__main__":
    main()
