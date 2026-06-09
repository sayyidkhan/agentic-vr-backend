# SceneVerse AI Backend

FastAPI backend for SceneVerse AI, an agentic movie companion that turns a paused cinematic scene into an interactive multi-agent world.

The backend MVP focuses on the core product loop:

```text
pause video -> analyze scene -> create agents -> chat with memory -> show orchestration trace
```

## Stack

- Python 3.13
- FastAPI
- SQLAlchemy + SQLite
- Docker for local and AWS EC2 runtime
- Mangum for optional Lambda deployments
- GitHub Actions CI
- AWS EC2 deployment

## Local Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Run tests:

```bash
cd backend
pytest
```

## Docker Smoke Checks

Normal FastAPI container:

```bash
docker build -f backend/Dockerfile -t sceneverse-backend:local backend
```

Optional Lambda container smoke image:

```bash
docker build --platform linux/amd64 -f backend/Dockerfile.lambda -t sceneverse-backend-lambda:local backend
```

## AWS Deployment

Current deployment path:

- AWS EC2 on Amazon Linux 2023 in `us-east-1`.
- The root `Dockerfile` runs the backend with `python:3.13-slim`.
- The app exposes `GET /` and `GET /health` for platform health checks.
- SQLite is stored inside the running container/instance, which is fine for MVP smoke but not durable production storage.

Live MVP deployment as of `2026-06-09`:

```text
Base URL: http://32.197.15.186
Swagger UI: http://32.197.15.186/docs
ReDoc: http://32.197.15.186/redoc
OpenAPI JSON: http://32.197.15.186/openapi.json
```

Verified live endpoints:

- `GET /`
- `GET /health`
- `POST /api/scenes/analyze`

Note: this EC2 instance currently uses an ephemeral public IP. If the instance is stopped and started again, the public IP and docs URL may change unless an Elastic IP is attached.

## CI/CD Status

Current state:

- CI is available in GitHub Actions.
- CD to the live EC2 deployment is manual.
- The Lambda deploy workflow exists, but it is not the live runtime path.

CI workflow:

- [`.github/workflows/backend-ci.yml`](.github/workflows/backend-ci.yml)
- Runs on pull requests and qualifying pushes.
- Checks Python install, compile step, `pytest`, FastAPI Docker build, and Lambda Docker build.

Manual-only deploy workflow:

- [`.github/workflows/deploy-aws-lambda.yml`](.github/workflows/deploy-aws-lambda.yml)
- Triggered only by `workflow_dispatch`
- Not wired to the live EC2 instance

Reason the live deployment is still manual:

- The current production backend runs on a single EC2 instance in `us-east-1`.
- That instance was bootstrapped by user data that cloned the repo, built Docker locally, and ran the container.
- GitHub Actions does not currently push code or images to that EC2 instance after merges.
- The Lambda path is retained as an optional future path, but this AWS account has had SCP-related restrictions on some deploy operations.

## Manual CD Runbook

This is the current deploy path for the live EC2 backend.

1. Push backend changes to the branch you want deployed.
2. Make sure CI passed in GitHub Actions.
3. Connect to the EC2 instance using your preferred AWS access path.
4. On the instance, update the checked-out repo and rebuild the container:

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

5. Smoke test the deployment:

```bash
curl -fsS http://32.197.15.186/health
curl -fsS http://32.197.15.186/
curl -fsS http://32.197.15.186/docs > /dev/null
```

6. If needed, verify the container directly:

```bash
docker ps
docker logs --tail=100 sceneverse-backend
```

Operational notes:

- This is manual CD, not automated CD.
- The instance currently uses an ephemeral public IP unless an Elastic IP is attached.
- SQLite data lives on that single host/container path, so this is acceptable for MVP only.

Useful files:

```text
Dockerfile
backend/Dockerfile
backend/app/main.py
```

More detail lives in [backend/README.md](backend/README.md) and [infra/aws/README.md](infra/aws/README.md).

## Current MVP Limits

- Scene parsing uses deterministic fallback data, not a real vision model yet.
- Research and Stripe paths are placeholders.
- There is no auth layer yet.
- SQLite is fine for hackathon/demo speed, but production should move to DynamoDB, RDS, or EFS-backed SQLite.
