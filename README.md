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
- GitHub Actions CI/CD
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

The Lambda workflow is currently manual-only because this AWS account has an AWS Organizations SCP explicitly denying Lambda function creation and ECR repository creation for the GitHub deploy role.

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
