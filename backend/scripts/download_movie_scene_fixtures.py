from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT_DIR / "tests" / "fixtures" / "movie_scene_cases.json"
OUTPUT_DIR = ROOT_DIR / "tests" / "fixtures" / "movie_images"
USER_AGENT = "Mozilla/5.0 (Codex Scene Fixture Downloader)"


def load_cases() -> list[dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def download_file(url: str, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        print(f"[skip] {destination.name} already exists")
        return

    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())
    print(f"[ok] downloaded {destination.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download movie poster fixtures used by scene analysis tests.")
    parser.add_argument("--force", action="store_true", help="Re-download files even if they already exist.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for case in load_cases():
        destination = OUTPUT_DIR / case["fileName"]
        download_file(case["imageUrl"], destination, force=args.force)


if __name__ == "__main__":
    main()
