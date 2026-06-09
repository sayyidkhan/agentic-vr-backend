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
  ENVIRONMENT
  DATABASE_URL
  FRONTEND_URL
  CORS_ORIGINS
  BEDROCK_REGION
  BEDROCK_MODEL_ID
  MODEL_REGISTRY_PATH
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
  EXA_API_KEY
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
  STRIPE_CURRENCY
  STRIPE_UNLOCK_AMOUNT_CENTS
  AWS_REGION
  MEDIA_STORAGE_BACKEND
  MEDIA_STORAGE_PREFIX
  S3_VIDEO_BUCKET
  MEDIA_CDN_BASE_URL
  AWS_BEARER_TOKEN_BEDROCK
)

TEMP_ENV_FILE="$(mktemp)"
trap 'rm -f "$TEMP_ENV_FILE"' EXIT

SYNC_KEYS_CSV="$(IFS=,; echo "${SYNC_KEYS[*]}")"
LOCAL_ENV_FILE_ABS="$ROOT_DIR/$LOCAL_ENV_FILE"

LOCAL_ENV_FILE="$LOCAL_ENV_FILE_ABS" SYNC_KEYS_CSV="$SYNC_KEYS_CSV" python - <<'PY' > "$TEMP_ENV_FILE"
from __future__ import annotations

import os
from pathlib import Path

env_path = Path(os.environ["LOCAL_ENV_FILE"])
sync_keys = [key for key in os.environ["SYNC_KEYS_CSV"].split(",") if key]

parsed: dict[str, str] = {}
for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    parsed[key] = value

for key in sync_keys:
    value = os.environ.get(key, parsed.get(key))
    if value:
        print(f"{key}={value}")
PY

log "Prepared runtime env from ${LOCAL_ENV_FILE}"

SCP_CMD=(scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
SSH_CMD=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_KEY_PATH" ]]; then
  SCP_CMD+=(-i "$SSH_KEY_PATH")
  SSH_CMD+=(-i "$SSH_KEY_PATH")
fi
SSH_CMD+=("$REMOTE_HOST")

REMOTE_TEMP_FILE="/tmp/sceneverse.shared.env"
"${SCP_CMD[@]}" "$TEMP_ENV_FILE" "${REMOTE_HOST}:${REMOTE_TEMP_FILE}"
"${SSH_CMD[@]}" "sudo mkdir -p \"$(dirname "$REMOTE_ENV_FILE")\" && sudo mv \"$REMOTE_TEMP_FILE\" \"$REMOTE_ENV_FILE\" && sudo chmod 600 \"$REMOTE_ENV_FILE\""

log "Synced runtime env to ${REMOTE_HOST}:${REMOTE_ENV_FILE}"
