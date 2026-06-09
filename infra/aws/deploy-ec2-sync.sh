#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-sceneverse-prod}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/sceneverse}"
REMOTE_STAGING_DIR="${REMOTE_STAGING_DIR:-/home/ec2-user/sceneverse-staging}"
REMOTE_DATA_DIR="${REMOTE_DATA_DIR:-/opt/sceneverse-data}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-/opt/sceneverse-config/shared.env}"
REMOTE_CONTAINER_NAME="${REMOTE_CONTAINER_NAME:-sceneverse-backend}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://18.207.53.115}"

APP_NAME="${APP_NAME:-SceneVerse AI Backend}"
SCENEVERSE_PROFILE="${SCENEVERSE_PROFILE:-cloud}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-prod}"
DATABASE_URL="${DATABASE_URL:-sqlite:///./data/sceneverse.db}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"
CORS_ORIGINS="${CORS_ORIGINS:-*}"

SSH_KEY_PATH="${SSH_KEY_PATH:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

build_ssh_rsh() {
  local -a cmd=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
  if [[ -n "$SSH_KEY_PATH" ]]; then
    cmd+=(-i "$SSH_KEY_PATH")
  fi
  printf '%q ' "${cmd[@]}"
}

log() {
  printf '[deploy-ec2] %s\n' "$*"
}

retry_curl() {
  local url="$1"
  local attempts="${2:-10}"
  local delay_seconds="${3:-2}"
  local attempt

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl -fsS "$url"; then
      return 0
    fi

    if [[ "$attempt" -lt "$attempts" ]]; then
      log "Health check not ready yet for ${url} (attempt ${attempt}/${attempts}); retrying in ${delay_seconds}s"
      sleep "$delay_seconds"
    fi
  done

  return 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command git
require_command rsync
require_command ssh
require_command curl

SSH_RSH="$(build_ssh_rsh)"
SSH_CMD=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_KEY_PATH" ]]; then
  SSH_CMD+=(-i "$SSH_KEY_PATH")
fi
SSH_CMD+=("$REMOTE_HOST")

cd "$ROOT_DIR"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "This script must be run from inside the git repository." >&2
  exit 1
fi

if [[ -n "$(git status --short)" ]]; then
  log "Deploying with local uncommitted changes."
fi

log "Checking SSH connectivity to ${REMOTE_HOST}"
"${SSH_CMD[@]}" "echo connected >/dev/null"

log "Syncing local repository to ${REMOTE_HOST}:${REMOTE_STAGING_DIR}"
rsync -az --delete \
  --exclude '.git' \
  --exclude '.pytest_cache' \
  --exclude '.mypy_cache' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude '.aws-lambda-build' \
  -e "$SSH_RSH" \
  "${ROOT_DIR}/" "${REMOTE_HOST}:${REMOTE_STAGING_DIR}/"

log "Building and restarting ${REMOTE_CONTAINER_NAME} on ${REMOTE_HOST}"
REMOTE_SCRIPT_FILE="$(mktemp)"
trap 'rm -f "$REMOTE_SCRIPT_FILE"' EXIT

{
  printf 'set -euo pipefail\n'
  printf 'APP_NAME=%q\n' "$APP_NAME"
  printf 'SCENEVERSE_PROFILE=%q\n' "$SCENEVERSE_PROFILE"
  printf 'ENVIRONMENT_NAME=%q\n' "$ENVIRONMENT_NAME"
  printf 'DATABASE_URL=%q\n' "$DATABASE_URL"
  printf 'FRONTEND_URL=%q\n' "$FRONTEND_URL"
  printf 'CORS_ORIGINS=%q\n' "$CORS_ORIGINS"
  printf 'REMOTE_APP_DIR=%q\n' "$REMOTE_APP_DIR"
  printf 'REMOTE_STAGING_DIR=%q\n' "$REMOTE_STAGING_DIR"
  printf 'REMOTE_DATA_DIR=%q\n' "$REMOTE_DATA_DIR"
  printf 'REMOTE_ENV_FILE=%q\n' "$REMOTE_ENV_FILE"
  printf 'REMOTE_CONTAINER_NAME=%q\n' "$REMOTE_CONTAINER_NAME"
  cat <<'REMOTE_SCRIPT'
set -euo pipefail

sudo mkdir -p "$REMOTE_DATA_DIR"
sudo mkdir -p "$(dirname "$REMOTE_ENV_FILE")"
sudo touch "$REMOTE_ENV_FILE"
sudo chmod 600 "$REMOTE_ENV_FILE"

if sudo docker ps -a --format '{{.Names}}' | grep -qx "$REMOTE_CONTAINER_NAME" && [[ ! -f "$REMOTE_DATA_DIR/sceneverse.db" ]]; then
  sudo docker cp "${REMOTE_CONTAINER_NAME}:/app/data/sceneverse.db" "$REMOTE_DATA_DIR/sceneverse.db" || true
fi

sudo mkdir -p "$REMOTE_APP_DIR"
sudo rsync -a --delete \
  --exclude '.git' \
  "$REMOTE_STAGING_DIR"/ "$REMOTE_APP_DIR"/

cd "$REMOTE_APP_DIR"
sudo docker build -t "${REMOTE_CONTAINER_NAME}:latest" .
sudo docker rm -f "$REMOTE_CONTAINER_NAME" >/dev/null 2>&1 || true
sudo docker run -d \
  --restart unless-stopped \
  --name "$REMOTE_CONTAINER_NAME" \
  -p 80:8000 \
  -v "$REMOTE_DATA_DIR:/app/data" \
  --env-file "$REMOTE_ENV_FILE" \
  -e APP_NAME="$APP_NAME" \
  -e SCENEVERSE_PROFILE="$SCENEVERSE_PROFILE" \
  -e ENVIRONMENT="$ENVIRONMENT_NAME" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e FRONTEND_URL="$FRONTEND_URL" \
  -e CORS_ORIGINS="$CORS_ORIGINS" \
  "${REMOTE_CONTAINER_NAME}:latest" >/dev/null

for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1/health >/dev/null && curl -fsS http://127.0.0.1/health/db >/dev/null; then
    break
  fi

  if [[ "$attempt" -eq 10 ]]; then
    echo "Remote health checks failed after ${attempt} attempts" >&2
    sudo docker logs --tail 200 "$REMOTE_CONTAINER_NAME" >&2 || true
    exit 1
  fi

  sleep 2
done

sudo docker ps --filter "name=${REMOTE_CONTAINER_NAME}"
REMOTE_SCRIPT
} > "$REMOTE_SCRIPT_FILE"

"${SSH_CMD[@]}" 'bash -se' < "$REMOTE_SCRIPT_FILE"
log "Running live smoke checks against ${PUBLIC_BASE_URL}"
retry_curl "${PUBLIC_BASE_URL}/health"
printf '\n'
retry_curl "${PUBLIC_BASE_URL}/health/db"
printf '\n'

rm -f "$REMOTE_SCRIPT_FILE"
trap - EXIT

log "Deploy complete."
