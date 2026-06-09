#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
  printf '[deploy-ec2-with-env] %s\n' "$*"
}

log "Syncing runtime env to EC2"
"${SCRIPT_DIR}/sync-ec2-env.sh"

log "Deploying backend code to EC2"
"${SCRIPT_DIR}/deploy-ec2-sync.sh"

log "Env sync and deploy complete."
