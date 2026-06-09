# SceneVerse AI Backend

FastAPI backend scaffold for the hackathon MVP.

## Run Locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

API docs:

```text
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/health
```

## Storage

The default database is SQLite:

```text
sqlite:///./data/sceneverse.db
```

This is good for local development and a controlled hackathon demo. On AWS, do not assume a container-local SQLite file is durable unless it is backed by persistent storage such as EFS. For a production path, move scene/session state to DynamoDB or RDS.

For the first AWS Lambda deployment, the CI/CD template sets:

```text
sqlite:////tmp/sceneverse.db
```

That keeps the demo backend writable on Lambda, but it is not durable across cold starts.

## MVP Endpoints

```text
POST /api/scenes/analyze
POST /api/chat
POST /api/research
POST /api/checkout
```

The current implementation returns deterministic fallback agent outputs and real `agentTrace` arrays. This is intentional: wire OpenAI, Exa, and Stripe after the core loop is stable.

## Python 3.13

The Docker images and GitHub Actions workflows use Python 3.13. AWS Lambda supports the `python3.13` runtime and Python 3.13 container base images.
