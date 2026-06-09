#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-southeast-2}"
SERVICE_NAME="${SERVICE_NAME:-sceneverse-backend}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-prod}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"
CORS_ORIGINS="${CORS_ORIGINS:-*}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${ROOT_DIR}/.aws-lambda-build"
PACKAGE_DIR="${BUILD_DIR}/package"
ZIP_FILE="${BUILD_DIR}/${SERVICE_NAME}-${ENVIRONMENT_NAME}.zip"
FUNCTION_NAME="${SERVICE_NAME}-${ENVIRONMENT_NAME}"
EXECUTION_ROLE_NAME="${FUNCTION_NAME}-lambda-role"

rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR"

python -m pip install --upgrade pip
python -m pip install -r "${ROOT_DIR}/backend/requirements.txt" --target "$PACKAGE_DIR"
cp -R "${ROOT_DIR}/backend/app" "${PACKAGE_DIR}/app"
find "$PACKAGE_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +

python - "$PACKAGE_DIR" "$ZIP_FILE" <<'PY'
from pathlib import Path
from sys import argv
from zipfile import ZIP_DEFLATED, ZipFile

package_dir = Path(argv[1])
zip_file = Path(argv[2])
zip_file.parent.mkdir(parents=True, exist_ok=True)

with ZipFile(zip_file, "w", ZIP_DEFLATED) as archive:
    for path in sorted(package_dir.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(package_dir))
PY

TRUST_POLICY_FILE="${BUILD_DIR}/lambda-trust-policy.json"
cat > "$TRUST_POLICY_FILE" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

ROLE_ARN="$(aws iam get-role --role-name "$EXECUTION_ROLE_NAME" --query "Role.Arn" --output text 2>/dev/null || true)"
if [[ -z "$ROLE_ARN" || "$ROLE_ARN" == "None" ]]; then
  ROLE_ARN="$(aws iam create-role \
    --role-name "$EXECUTION_ROLE_NAME" \
    --assume-role-policy-document "file://${TRUST_POLICY_FILE}" \
    --query "Role.Arn" \
    --output text)"
  aws iam attach-role-policy \
    --role-name "$EXECUTION_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  aws iam wait role-exists --role-name "$EXECUTION_ROLE_NAME"
  sleep 10
fi

ENVIRONMENT_FILE="${BUILD_DIR}/lambda-environment.json"
python - "$ENVIRONMENT_FILE" <<'PY'
import json
import os
from pathlib import Path
from sys import argv

payload = {
    "Variables": {
        "APP_NAME": "SceneVerse AI Backend",
        "ENVIRONMENT": os.environ.get("ENVIRONMENT_NAME", "prod"),
        "DATABASE_URL": "sqlite:////tmp/sceneverse.db",
        "FRONTEND_URL": os.environ.get("FRONTEND_URL", "http://localhost:5173"),
        "CORS_ORIGINS": os.environ.get("CORS_ORIGINS", "*"),
    }
}
Path(argv[1]).write_text(json.dumps(payload), encoding="utf-8")
PY

CORS_FILE="${BUILD_DIR}/lambda-url-cors.json"
python - "$CORS_FILE" <<'PY'
import json
import os
from pathlib import Path
from sys import argv

origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "*").split(",") if origin.strip()]
payload = {
    "AllowCredentials": False,
    "AllowHeaders": ["*"],
    "AllowMethods": ["*"],
    "AllowOrigins": origins or ["*"],
}
Path(argv[1]).write_text(json.dumps(payload), encoding="utf-8")
PY

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://${ZIP_FILE}" \
    --region "$AWS_REGION" >/dev/null
  aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$AWS_REGION"
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.13 \
    --handler app.lambda_handler.handler \
    --role "$ROLE_ARN" \
    --architectures x86_64 \
    --timeout 60 \
    --memory-size 1024 \
    --environment "file://${ENVIRONMENT_FILE}" \
    --region "$AWS_REGION" >/dev/null
  aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$AWS_REGION"
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.13 \
    --handler app.lambda_handler.handler \
    --role "$ROLE_ARN" \
    --zip-file "fileb://${ZIP_FILE}" \
    --architectures x86_64 \
    --timeout 60 \
    --memory-size 1024 \
    --environment "file://${ENVIRONMENT_FILE}" \
    --region "$AWS_REGION" >/dev/null
  aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$AWS_REGION"
fi

if aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  aws lambda update-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --auth-type NONE \
    --cors "file://${CORS_FILE}" \
    --region "$AWS_REGION" >/dev/null
else
  aws lambda create-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --auth-type NONE \
    --cors "file://${CORS_FILE}" \
    --region "$AWS_REGION" >/dev/null
fi

ADD_PERMISSION_OUTPUT="$(aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id FunctionUrlAllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$AWS_REGION" 2>&1)" || {
  if [[ "$ADD_PERMISSION_OUTPUT" != *"ResourceConflictException"* ]]; then
    echo "$ADD_PERMISSION_OUTPUT" >&2
    exit 1
  fi
}

FUNCTION_URL="$(aws lambda get-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --query "FunctionUrl" \
  --output text \
  --region "$AWS_REGION")"

echo "Function URL: ${FUNCTION_URL}"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "function_url=${FUNCTION_URL}" >> "$GITHUB_OUTPUT"
fi
