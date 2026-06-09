# AWS Deployment Notes

## Active Path: EC2 Docker

This AWS account has had AWS Organizations Service Control Policy restrictions that blocked parts of the Lambda and registry-based deploy path. The practical live deployment path right now is a manually managed EC2 instance running Docker.

Target:

- Platform: EC2 on Amazon Linux 2023 in `us-east-1`
- Runtime: `python:3.13-slim` from the root `Dockerfile`
- API exposure: public EC2 IP / DNS
- MVP database: SQLite inside the running container
- Health checks: `GET /` and `GET /health`

Live endpoint as of `2026-06-09`:

```text
Base URL: http://32.197.15.186
Swagger UI: http://32.197.15.186/docs
ReDoc: http://32.197.15.186/redoc
OpenAPI JSON: http://32.197.15.186/openapi.json
```

Recommended environment variables:

```text
APP_NAME=SceneVerse AI Backend
ENVIRONMENT=prod
DATABASE_URL=sqlite:///./data/sceneverse.db
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=*
```

## CI/CD Reality

- CI is automated with GitHub Actions.
- CD to the live EC2 environment is manual.
- There is no GitHub Actions workflow currently redeploying the EC2 host on merge.

Manual EC2 deploy steps:

```bash
cd /opt/sceneverse
git pull origin main
docker build -t sceneverse-backend:latest .
docker rm -f sceneverse-backend || true
docker run -d \
  --restart unless-stopped \
  --name sceneverse-backend \
  -p 80:8000 \
  -e APP_NAME="SceneVerse AI Backend" \
  -e ENVIRONMENT=prod \
  -e DATABASE_URL=sqlite:///./data/sceneverse.db \
  -e FRONTEND_URL=http://localhost:5173 \
  -e CORS_ORIGINS='*' \
  sceneverse-backend:latest
```

Post-deploy smoke test:

```bash
curl -fsS http://32.197.15.186/health
curl -fsS http://32.197.15.186/
curl -fsS http://32.197.15.186/docs > /dev/null
```

## Optional Path: Lambda Zip

The Lambda workflow and helper scripts are retained for an AWS account where Lambda creation is allowed.

Files:

```text
.github/workflows/deploy-aws-lambda.yml
infra/aws/bootstrap-github-actions.sh
infra/aws/deploy-lambda-zip.sh
infra/aws/lambda-app.yml
```

The Lambda workflow is manual-only in this repo and is not the current live deployment path.
