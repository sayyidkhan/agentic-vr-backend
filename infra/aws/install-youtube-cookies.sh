#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-sceneverse-prod}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-/opt/sceneverse-config/shared.env}"
REMOTE_COOKIES_FILE="${REMOTE_COOKIES_FILE:-/opt/sceneverse-config/youtube-cookies.txt}"
REMOTE_TEMP_FILE="${REMOTE_TEMP_FILE:-/tmp/sceneverse-youtube-cookies.txt}"
SSH_KEY_PATH="${SSH_KEY_PATH:-}"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/youtube-cookies.txt" >&2
  exit 2
fi

LOCAL_COOKIES_FILE="$1"

if [[ ! -f "$LOCAL_COOKIES_FILE" ]]; then
  echo "Local cookies file not found: $LOCAL_COOKIES_FILE" >&2
  exit 1
fi

SCP_CMD=(scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
SSH_CMD=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_KEY_PATH" ]]; then
  SCP_CMD+=(-i "$SSH_KEY_PATH")
  SSH_CMD+=(-i "$SSH_KEY_PATH")
fi
SSH_CMD+=("$REMOTE_HOST")

REMOTE_SCRIPT_FILE="$(mktemp)"
trap 'rm -f "$REMOTE_SCRIPT_FILE"' EXIT

"${SCP_CMD[@]}" "$LOCAL_COOKIES_FILE" "${REMOTE_HOST}:${REMOTE_TEMP_FILE}"

{
  printf 'set -euo pipefail\n'
  printf 'REMOTE_ENV_FILE=%q\n' "$REMOTE_ENV_FILE"
  printf 'REMOTE_COOKIES_FILE=%q\n' "$REMOTE_COOKIES_FILE"
  printf 'REMOTE_TEMP_FILE=%q\n' "$REMOTE_TEMP_FILE"
  cat <<'REMOTE_SCRIPT'
sudo mkdir -p "$(dirname "$REMOTE_COOKIES_FILE")"
sudo install -m 600 -o root -g root "$REMOTE_TEMP_FILE" "$REMOTE_COOKIES_FILE"
rm -f "$REMOTE_TEMP_FILE"

sudo env REMOTE_ENV_FILE="$REMOTE_ENV_FILE" YTDLP_COOKIES_FILE_VALUE="$REMOTE_COOKIES_FILE" python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ["REMOTE_ENV_FILE"])
path.parent.mkdir(parents=True, exist_ok=True)
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
key = "YTDLP_COOKIES_FILE"
value = os.environ["YTDLP_COOKIES_FILE_VALUE"]

updated: list[str] = []
written = False
for line in lines:
    if line.startswith(f"{key}="):
        if not written:
            updated.append(f"{key}={value}")
            written = True
        continue
    updated.append(line)

if not written:
    if updated and updated[-1].strip():
        updated.append("")
    updated.append(f"{key}={value}")

path.write_text("\n".join(updated) + "\n", encoding="utf-8")
path.chmod(0o600)
PY

echo "Installed YouTube cookies at $REMOTE_COOKIES_FILE and configured YTDLP_COOKIES_FILE."
REMOTE_SCRIPT
} > "$REMOTE_SCRIPT_FILE"

"${SSH_CMD[@]}" 'bash -se' < "$REMOTE_SCRIPT_FILE"
