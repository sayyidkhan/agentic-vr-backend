# SceneVerse AI Backend

FastAPI backend for SceneVerse AI, a web-first agentic movie companion that turns a paused cinematic scene into an interactive multi-agent world.

The backend is intentionally scoped for a hackathon MVP:

```text
pause video -> analyze scene -> create agents -> chat with memory -> show orchestration trace
```

It currently uses deterministic fallback agents and SQLite so the product loop can be tested before wiring paid or external services.

## What This Backend Does

- Accepts a paused frame, timestamp, transcript segment, and video metadata.
- Generates a structured scene context with fallback demo data.
- Creates character cards with goals, emotional state, and knowledge boundaries.
- Routes chat through a lightweight orchestrator.
- Supports Character Agent, Director Agent, Memory Agent, and placeholder Research Agent flows.
- Persists scene state, characters, conversation turns, and research summaries in SQLite.
- Returns `agentTrace` arrays so the frontend can show visible multi-agent coordination.
- Provides a simulated Stripe unlock path until real Stripe Checkout is wired.

## Tech Stack

- Python 3.13 target runtime
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite for MVP persistence
- Mangum for AWS Lambda zip deployment
- Docker
- GitHub Actions CI/CD
- AWS Lambda Function URL deployment path

## Project Structure

```text
backend/
  app/
    main.py                  # FastAPI app and API routes
    lambda_handler.py        # AWS Lambda Mangum adapter
    config.py                # Environment config
    database.py              # SQLAlchemy engine/session setup
    agents/
      scene_parser.py
      orchestrator.py
      character_agent.py
      director_agent.py
      memory_agent.py
      research_agent.py
    models/
      schemas.py             # API request/response models
      db.py                  # SQLAlchemy records
    services/
      checkout.py            # Stripe/simulated checkout service
    store/
      sqlite_store.py        # SQLite persistence adapter
    data/
      fallback_scene.json    # Reliable demo fallback scene
  tests/
    test_api_smoke.py
  Dockerfile                 # Normal FastAPI container
  Dockerfile.lambda          # Optional local Lambda container smoke image
  requirements.txt
  requirements-dev.txt
  pyproject.toml
```

## Prerequisites

Recommended:

- Python 3.13
- Docker Desktop
- GitHub CLI, optional but useful for repo secrets

Local macOS may still point `python3` at Python 3.9. The code is currently compatible with Python 3.9 for local smoke tests, but CI and Docker target Python 3.13.

To install Python 3.13 with `pyenv`:

```bash
pyenv install 3.13
pyenv local 3.13
```

## Local Setup

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/health
```

## Environment Variables

Copy `.env.example` to `.env`.

```text
APP_NAME=SceneVerse AI Backend
ENVIRONMENT=local
DATABASE_URL=sqlite:///./data/sceneverse.db
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
FRONTEND_URL=http://localhost:5173

OPENAI_API_KEY=
EXA_API_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
```

Current behavior:

- `OPENAI_API_KEY` is not used yet.
- `EXA_API_KEY` is not used yet.
- Empty Stripe keys return a simulated unlock URL.

## Run Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

The smoke test covers:

- `GET /health`
- `POST /api/scenes/analyze`
- `POST /api/chat`
- `POST /api/research`
- `POST /api/checkout`

## API Endpoints

### `GET /health`

Checks API availability.

Example:

```bash
curl http://localhost:8000/health
```

### `POST /api/scenes/analyze`

Creates scene context from a paused frame.

Example:

```bash
curl -X POST http://localhost:8000/api/scenes/analyze \
  -H "content-type: application/json" \
  -d '{
    "frame": "data:image/jpeg;base64,demo",
    "timestamp": 42.5,
    "transcriptSegment": "You said this place was safe.",
    "videoMetadata": {
      "videoId": "demo-clip",
      "title": "Demo Clip"
    }
  }'
```

Response includes:

- `sceneId`
- `sceneSummary`
- `scene`
- `characters`
- `directorContext`
- `memorySummary`
- `agentTrace`

### `POST /api/chat`

Sends a user message into the scene agent system.

Example:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "content-type: application/json" \
  -d '{
    "sceneId": "scene_xxx",
    "message": "What are you feeling right now?",
    "targetAgentId": "scene_xxx_maya"
  }'
```

Routing behavior:

- Character-style questions go to a Character Agent.
- Meta/story questions go to the Director Agent.
- External-context questions go through the Research Agent placeholder, then Director Agent.

### `POST /api/research`

Returns placeholder research context for now.

Example:

```bash
curl -X POST http://localhost:8000/api/research \
  -H "content-type: application/json" \
  -d '{
    "sceneId": "scene_xxx",
    "query": "What genre references does this scene evoke?"
  }'
```

### `POST /api/checkout`

Returns a Stripe Checkout URL when Stripe is wired, otherwise a simulated unlock URL.

Example:

```bash
curl -X POST http://localhost:8000/api/checkout \
  -H "content-type: application/json" \
  -d '{
    "sceneId": "scene_xxx",
    "unlockType": "premium_scene"
  }'
```

## SQLite Storage

Default local database:

```text
sqlite:///./data/sceneverse.db
```

Tables:

- `scenes`
- `characters`
- `conversation_turns`
- `research_contexts`

SQLite is good for:

- local development
- demo persistence
- controlled hackathon flows

SQLite is not good for:

- multi-instance production APIs
- durable AWS Lambda local storage
- high-concurrency writes

For the first AWS Lambda deployment, the CI/CD workflow sets:

```text
sqlite:////tmp/sceneverse.db
```

That keeps the Lambda function writable, but `/tmp` is not durable across cold starts. For production, move to DynamoDB or RDS. If you insist on durable SQLite in AWS, mount EFS and point `DATABASE_URL` at that mounted path.

## Docker

Build the normal FastAPI container:

```bash
docker build -f backend/Dockerfile -t sceneverse-backend:local backend
```

Run it:

```bash
docker run --rm \
  --name sceneverse-backend-smoke \
  -p 8012:8000 \
  -e DATABASE_URL=sqlite:///./data/smoke.db \
  sceneverse-backend:local
```

Smoke check:

```bash
curl http://localhost:8012/health
```

Build the AWS Lambda container:

```bash
docker build --platform linux/amd64 \
  -f backend/Dockerfile.lambda \
  -t sceneverse-backend-lambda:local \
  backend
```

Run the Lambda image locally:

```bash
docker run --rm \
  --platform linux/amd64 \
  --name sceneverse-lambda-smoke \
  -p 9000:8080 \
  -e DATABASE_URL=sqlite:////tmp/sceneverse-smoke.db \
  sceneverse-backend-lambda:local
```

Invoke a health event:

```bash
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "content-type: application/json" \
  -d '{
    "version": "2.0",
    "routeKey": "GET /health",
    "rawPath": "/health",
    "rawQueryString": "",
    "headers": {
      "content-type": "application/json"
    },
    "requestContext": {
      "http": {
        "method": "GET",
        "path": "/health",
        "protocol": "HTTP/1.1",
        "sourceIp": "127.0.0.1",
        "userAgent": "curl"
      },
      "requestId": "local",
      "routeKey": "GET /health",
      "stage": "$default"
    },
    "isBase64Encoded": false
  }'
```

## CI/CD

GitHub Actions workflows live in:

```text
.github/workflows/backend-ci.yml
.github/workflows/deploy-aws-lambda.yml
```

CI runs on backend changes and checks:

- Python 3.13 setup
- dependency install
- compile check
- pytest smoke test
- normal Docker build
- Lambda Docker build

Deployment target:

- AWS Lambda Function URL
- Python 3.13 Lambda zip package
- Direct Lambda create/update through GitHub Actions OIDC
- Public Lambda Function URL with `/health` smoke test

AWS infra files:

```text
infra/aws/deploy-lambda-zip.sh
infra/aws/lambda-app.yml
infra/aws/bootstrap-github-actions.sh
infra/aws/README.md
```

Before deployment, bootstrap GitHub OIDC from AWS CloudShell or an authenticated AWS CLI:

```bash
AWS_REGION=ap-southeast-2 \
GITHUB_OWNER=sayyidkhan \
GITHUB_REPO=agentic-vr-backend \
GITHUB_BRANCH=main \
bash infra/aws/bootstrap-github-actions.sh
```

Then set this GitHub secret:

```text
AWS_GITHUB_ACTIONS_ROLE_ARN=<printed role arn>
```

## Current Limitations

- Scene analysis uses fallback JSON, not a real vision LLM yet.
- Research Agent returns an Exa placeholder.
- Stripe Checkout is simulated unless `STRIPE_SECRET_KEY` integration is implemented.
- Memory is persisted in SQLite but summarized with deterministic logic.
- No auth, no user profiles, no creator upload flow.

## Next Backend Steps

Recommended order:

1. Wire OpenAI multimodal scene parsing in `agents/scene_parser.py`.
2. Add strict Pydantic validation for model-generated scene JSON.
3. Wire Exa in `agents/research_agent.py`.
4. Add real Stripe Checkout in `services/checkout.py`.
5. Replace or augment SQLite with DynamoDB/RDS for deployed persistence.
6. Add request logging and basic rate limiting.
7. Add frontend CORS origin once the deployed frontend URL is known.
