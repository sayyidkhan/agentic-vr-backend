#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AWS_PROFILE="${AWS_PROFILE:-sceneverse}"
AWS_REGION="${AWS_REGION:-us-east-1}"
DB_INSTANCE_ID="${DB_INSTANCE_ID:-sceneverse-postgres}"
DB_SECRET_ID="${DB_SECRET_ID:-sceneverse/rds/postgres}"
REMOTE_HOST="${REMOTE_HOST:-sceneverse-prod}"
LOCAL_DB_HOST="${LOCAL_DB_HOST:-127.0.0.1}"
LOCAL_DB_PORT="${LOCAL_DB_PORT:-15432}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  python_bin="$PYTHON_BIN"
elif [[ -x ".venv/bin/python" ]]; then
  python_bin=".venv/bin/python"
else
  python_bin="python3.13"
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

port_open() {
  "$python_bin" - "$LOCAL_DB_HOST" "$LOCAL_DB_PORT" <<'PY' >/dev/null 2>&1
from __future__ import annotations

import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.create_connection((host, port), timeout=1):
    pass
PY
}

require_command aws
require_command ssh
require_command "$python_bin"

rds_endpoint="$(
  AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
    aws rds describe-db-instances \
      --db-instance-identifier "$DB_INSTANCE_ID" \
      --query 'DBInstances[0].Endpoint.Address' \
      --output text
)"

secret_json="$(
  AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
    aws secretsmanager get-secret-value \
      --secret-id "$DB_SECRET_ID" \
      --query SecretString \
      --output text
)"

cloud_database_url="$(
  SECRET_JSON="$secret_json" LOCAL_DB_HOST="$LOCAL_DB_HOST" LOCAL_DB_PORT="$LOCAL_DB_PORT" "$python_bin" <<'PY'
from __future__ import annotations

import json
import os
from urllib.parse import quote

secret = json.loads(os.environ["SECRET_JSON"])
username = quote(secret["username"], safe="")
password = quote(secret["password"], safe="")
host = os.environ["LOCAL_DB_HOST"]
port = os.environ["LOCAL_DB_PORT"]
print(f"postgresql+psycopg://{username}:{password}@{host}:{port}/sceneverse")
PY
)"

tunnel_pid=""
backend_pid=""
cleanup() {
  if [[ -n "$backend_pid" ]]; then
    kill "$backend_pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "$tunnel_pid" ]]; then
    kill "$tunnel_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if port_open; then
  echo "Using existing local Postgres tunnel on ${LOCAL_DB_HOST}:${LOCAL_DB_PORT}"
else
  echo "Opening SSH tunnel ${LOCAL_DB_HOST}:${LOCAL_DB_PORT} -> ${rds_endpoint}:5432 via ${REMOTE_HOST}"
  ssh \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -N \
    -L "${LOCAL_DB_HOST}:${LOCAL_DB_PORT}:${rds_endpoint}:5432" \
    "$REMOTE_HOST" &
  tunnel_pid="$!"

  for _ in {1..20}; do
    if port_open; then
      break
    fi
    sleep 0.5
  done

  if ! port_open; then
    echo "Timed out waiting for local Postgres tunnel on ${LOCAL_DB_HOST}:${LOCAL_DB_PORT}" >&2
    exit 1
  fi
fi

export AWS_PROFILE
export AWS_REGION
export SCENEVERSE_PROFILE=cloud
export ENVIRONMENT=cloud
export DATABASE_URL="$cloud_database_url"
export CLOUD_DATABASE_URL="$cloud_database_url"
export MEDIA_STORAGE_BACKEND=s3
export FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://localhost:3000}"

if credential_exports="$(
  AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
    aws configure export-credentials --profile "$AWS_PROFILE" --format env
)"; then
  # The AWS CLI login profile can resolve credentials that boto3 cannot read
  # directly. Export short-lived env credentials so local S3 uploads work.
  eval "$credential_exports"
else
  echo "Unable to export AWS credentials for profile ${AWS_PROFILE}; run aws login before starting the backend." >&2
  exit 1
fi

echo "Starting local backend on http://${BACKEND_HOST}:${BACKEND_PORT} with cloud Postgres and S3 media"
"$python_bin" -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
backend_pid="$!"

while true; do
  if ! kill -0 "$backend_pid" >/dev/null 2>&1; then
    wait "$backend_pid"
    exit $?
  fi

  if [[ -n "$tunnel_pid" ]] && ! kill -0 "$tunnel_pid" >/dev/null 2>&1; then
    echo "Postgres SSH tunnel exited; stopping local backend" >&2
    kill "$backend_pid" >/dev/null 2>&1 || true
    wait "$backend_pid" >/dev/null 2>&1 || true
    exit 1
  fi

  sleep 2
done
