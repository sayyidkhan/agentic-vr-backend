#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-sceneverse-prod}"
LOCAL_ENV_FILE="${LOCAL_ENV_FILE:-backend/.env}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-/opt/sceneverse-config/shared.env}"
SSH_KEY_PATH="${SSH_KEY_PATH:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log() {
  printf '[sync-ec2-env] %s\n' "$*"
}

cd "$ROOT_DIR"

if [[ ! -f "$LOCAL_ENV_FILE" ]]; then
  echo "Local env file not found: $LOCAL_ENV_FILE" >&2
  exit 1
fi

SYNC_KEYS=(
  APP_NAME
  SCENEVERSE_PROFILE
  ENVIRONMENT
  DATABASE_URL
  LOCAL_DATABASE_URL
  CLOUD_DATABASE_URL
  FRONTEND_URL
  CORS_ORIGINS
  BEDROCK_REGION
  BEDROCK_MODEL_ID
  MODEL_REGISTRY_PATH
  VOICE_REGISTRY_PATH
  ENABLE_LIVE_SCENE_ANALYSIS
  SCENE_ANALYSIS_MODEL_ID
  ENABLE_EXA_CHARACTER_ENRICHMENT
  SCENE_ANALYSIS_MAX_CHARACTERS
  ENABLE_LIVE_CHARACTER_CHAT
  CHARACTER_CHAT_MODEL_ID
  OPENAI_API_KEY
  OPENAI_REALTIME_TRANSCRIPTION_MODEL
  OPENAI_REALTIME_TOKEN_TTL_SECONDS
  OPENAI_REALTIME_VAD_THRESHOLD
  OPENAI_REALTIME_VAD_PREFIX_PADDING_MS
  OPENAI_REALTIME_VAD_SILENCE_DURATION_MS
  SPEECHMATICS_API_KEY
  SPEECHMATICS_TTS_OUTPUT_FORMAT
  ELEVENLABS_API_KEY
  ELEVENLABS_TTS_MODEL_ID
  ELEVENLABS_OUTPUT_FORMAT
  EXA_API_KEY
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
  STRIPE_CURRENCY
  STRIPE_UNLOCK_AMOUNT_CENTS
  AWS_REGION
  MEDIA_STORAGE_BACKEND
  LOCAL_MEDIA_LOCAL_DIR
  LOCAL_MEDIA_PUBLIC_PATH
  LOCAL_MEDIA_STORAGE_PREFIX
  CLOUD_MEDIA_LOCAL_DIR
  CLOUD_MEDIA_PUBLIC_PATH
  CLOUD_MEDIA_STORAGE_PREFIX
  MEDIA_STORAGE_PREFIX
  S3_VIDEO_BUCKET
  CLOUD_S3_VIDEO_BUCKET
  MEDIA_CDN_BASE_URL
  CLOUD_MEDIA_CDN_BASE_URL
  YTDLP_COOKIES_FILE
  YTDLP_USER_AGENT
  YTDLP_POT_PROVIDER_BASE_URL
  AWS_BEARER_TOKEN_BEDROCK
)

TEMP_ENV_FILE="$(mktemp)"
REMOTE_ENV_CACHE="$(mktemp)"
trap 'rm -f "$TEMP_ENV_FILE" "$REMOTE_ENV_CACHE"' EXIT

SCP_CMD=(scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
SSH_CMD=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_KEY_PATH" ]]; then
  SCP_CMD+=(-i "$SSH_KEY_PATH")
  SSH_CMD+=(-i "$SSH_KEY_PATH")
fi
SSH_CMD+=("$REMOTE_HOST")

if "${SSH_CMD[@]}" "sudo test -f \"$REMOTE_ENV_FILE\""; then
  "${SSH_CMD[@]}" "sudo cat \"$REMOTE_ENV_FILE\"" > "$REMOTE_ENV_CACHE" || true
fi

SYNC_KEYS_CSV="$(IFS=,; echo "${SYNC_KEYS[*]}")"
LOCAL_ENV_FILE_ABS="$ROOT_DIR/$LOCAL_ENV_FILE"

LOCAL_ENV_FILE="$LOCAL_ENV_FILE_ABS" SYNC_KEYS_CSV="$SYNC_KEYS_CSV" REMOTE_ENV_CACHE="$REMOTE_ENV_CACHE" python - <<'PY' > "$TEMP_ENV_FILE"
from __future__ import annotations

import os
from pathlib import Path


def parse_env(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        parsed[key] = value
    return parsed


def is_dev_database_url(value: str) -> bool:
    lowered = value.lower()
    return "127.0.0.1" in lowered or "localhost" in lowered


env_path = Path(os.environ["LOCAL_ENV_FILE"])
remote_path = Path(os.environ["REMOTE_ENV_CACHE"])
sync_keys = [key for key in os.environ["SYNC_KEYS_CSV"].split(",") if key]

parsed = parse_env(env_path)
remote_parsed = parse_env(remote_path)

for key in sync_keys:
    local_value = os.environ.get(key, parsed.get(key, "")).strip()
    remote_value = remote_parsed.get(key, "").strip()

    if key in {"DATABASE_URL", "CLOUD_DATABASE_URL"} and local_value and is_dev_database_url(local_value):
        value = remote_value or local_value
    else:
        value = local_value or remote_value

    if value:
        print(f"{key}={value}")
PY

log "Prepared runtime env from ${LOCAL_ENV_FILE} (merged with remote when needed)"

REMOTE_TEMP_FILE="/tmp/sceneverse.shared.env"
"${SCP_CMD[@]}" "$TEMP_ENV_FILE" "${REMOTE_HOST}:${REMOTE_TEMP_FILE}"
"${SSH_CMD[@]}" "sudo mkdir -p \"$(dirname "$REMOTE_ENV_FILE")\" && sudo mv \"$REMOTE_TEMP_FILE\" \"$REMOTE_ENV_FILE\" && sudo chmod 600 \"$REMOTE_ENV_FILE\""

log "Synced runtime env to ${REMOTE_HOST}:${REMOTE_ENV_FILE}"
