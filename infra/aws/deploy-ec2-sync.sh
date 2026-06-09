#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-sceneverse-prod}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/sceneverse}"
REMOTE_STAGING_DIR="${REMOTE_STAGING_DIR:-/home/ec2-user/sceneverse-staging}"
REMOTE_DATA_DIR="${REMOTE_DATA_DIR:-/opt/sceneverse-data}"
REMOTE_CONTAINER_NAME="${REMOTE_CONTAINER_NAME:-sceneverse-backend}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://18.207.53.115}"

APP_NAME="${APP_NAME:-SceneVerse AI Backend}"
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
  printf 'ENVIRONMENT_NAME=%q\n' "$ENVIRONMENT_NAME"
  printf 'DATABASE_URL=%q\n' "$DATABASE_URL"
  printf 'FRONTEND_URL=%q\n' "$FRONTEND_URL"
  printf 'CORS_ORIGINS=%q\n' "$CORS_ORIGINS"
  printf 'REMOTE_APP_DIR=%q\n' "$REMOTE_APP_DIR"
  printf 'REMOTE_STAGING_DIR=%q\n' "$REMOTE_STAGING_DIR"
  printf 'REMOTE_DATA_DIR=%q\n' "$REMOTE_DATA_DIR"
  printf 'REMOTE_CONTAINER_NAME=%q\n' "$REMOTE_CONTAINER_NAME"
  cat <<'REMOTE_SCRIPT'
set -euo pipefail

sudo mkdir -p "$REMOTE_DATA_DIR"

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
  -e APP_NAME="$APP_NAME" \
  -e ENVIRONMENT="$ENVIRONMENT_NAME" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e FRONTEND_URL="$FRONTEND_URL" \
  -e CORS_ORIGINS="$CORS_ORIGINS" \
  "${REMOTE_CONTAINER_NAME}:latest" >/dev/null

sleep 2
curl -fsS http://127.0.0.1/health >/dev/null
curl -fsS http://127.0.0.1/health/db >/dev/null
sudo docker ps --filter "name=${REMOTE_CONTAINER_NAME}"
REMOTE_SCRIPT
} > "$REMOTE_SCRIPT_FILE"

"${SSH_CMD[@]}" 'bash -se' < "$REMOTE_SCRIPT_FILE"
rm -f "$REMOTE_SCRIPT_FILE"
trap - EXIT

log "Running live smoke checks against ${PUBLIC_BASE_URL}"
curl -fsS "${PUBLIC_BASE_URL}/health"
printf '\n'
curl -fsS "${PUBLIC_BASE_URL}/health/db"
printf '\n'

log "Deploy complete."
