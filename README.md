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
- Mangum for AWS Lambda
- Docker for local container smoke checks
- GitHub Actions CI/CD
- AWS Lambda Function URL deployment

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

- GitHub Actions assumes an AWS IAM role through OIDC.
- The workflow packages the app as a Python 3.13 Lambda zip.
- The workflow creates or updates `sceneverse-backend-prod`.
- The API is exposed through a public Lambda Function URL.
- SQLite is stored at `/tmp/sceneverse.db`, which is writable but not durable across cold starts.

Required GitHub secret:

```text
AWS_GITHUB_ACTIONS_ROLE_ARN=arn:aws:iam::<account-id>:role/sceneverse-backend-github-actions
```

Deploy workflow:

```text
.github/workflows/deploy-aws-lambda.yml
```

AWS helper scripts:

```text
infra/aws/bootstrap-github-actions.sh
infra/aws/deploy-lambda-zip.sh
```

More detail lives in [backend/README.md](backend/README.md) and [infra/aws/README.md](infra/aws/README.md).

## Current MVP Limits

- Scene parsing uses deterministic fallback data, not a real vision model yet.
- Research and Stripe paths are placeholders.
- There is no auth layer yet.
- SQLite is fine for hackathon/demo speed, but production should move to DynamoDB, RDS, or EFS-backed SQLite.
