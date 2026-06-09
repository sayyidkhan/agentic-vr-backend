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
- Docker for local and AWS Elastic Beanstalk runtime
- Mangum for optional Lambda deployments
- GitHub Actions CI/CD
- AWS Elastic Beanstalk Docker deployment

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

- AWS Elastic Beanstalk Docker on Amazon Linux 2023.
- The root `Dockerfile` runs the backend with `python:3.13-slim`.
- The app exposes `GET /` and `GET /health` for platform health checks.
- SQLite is stored inside the running container/instance, which is fine for MVP smoke but not durable production storage.

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
