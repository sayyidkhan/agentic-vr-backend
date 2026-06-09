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
- SQLite is mounted from `/opt/sceneverse-data/sceneverse.db` on the EC2 host, which is acceptable for MVP but still single-host storage.

Live MVP deployment as of `2026-06-09`:

```text
Base URL: http://18.207.53.115
Swagger UI: http://18.207.53.115/docs
ReDoc: http://18.207.53.115/redoc
OpenAPI JSON: http://18.207.53.115/openapi.json
```

AWS networking note:

- An AWS Elastic IP was allocated and associated to the EC2 instance.
- That Elastic IP is `18.207.53.115`.
- This keeps the deploy URL and SSH target stable across EC2 stop/start cycles.

Verified live endpoints:

- `GET /`
- `GET /health`
- `GET /health/db`
- `POST /api/scenes/analyze`

Note: this EC2 instance now has an Elastic IP attached, so the public URL is stable across stop/start cycles.

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

1. Make sure your local machine can SSH to the instance.
2. From the repo root, run:

```bash
./infra/aws/deploy-ec2-sync.sh
```

3. Smoke test the deployment:

```bash
curl -fsS http://18.207.53.115/health
curl -fsS http://18.207.53.115/health/db
curl -fsS http://18.207.53.115/
curl -fsS http://18.207.53.115/docs > /dev/null
```

4. If needed, verify the container directly:

```bash
docker ps
docker logs --tail=100 sceneverse-backend
```

SSH notes:

- Expected SSH alias: `sceneverse-prod`
- Expected local key: `~/.ssh/sceneverse_ec2`
- Expected SSH user: `ec2-user`
- Port `22` must be open in the EC2 Security Group for your current public IP as `/32`

Recommended SSH config:

```sshconfig
Host sceneverse-prod
  HostName 18.207.53.115
  User ec2-user
  IdentityFile ~/.ssh/sceneverse_ec2
  IdentitiesOnly yes
```

If SSH is not bootstrapped yet:

- use AWS CloudShell or EC2 Instance Connect to push a temporary public key
- SSH in once
- append your durable local public key into `/home/ec2-user/.ssh/authorized_keys`
- verify with `ssh sceneverse-prod`

Does SSH expire?

- normal SSH access with `~/.ssh/sceneverse_ec2` does not expire automatically
- temporary EC2 Instance Connect bootstrap access does expire
- if direct SSH stops working later, usually the cause is changed `authorized_keys`, changed local/public IP, or a host key trust mismatch, not key expiry

Operational notes:

- This is still manual CD, but it is now scriptable and repeatable from a local machine.
- The instance currently uses an Elastic IP, so the public URL should remain stable.
- If SSH fails with `Host key verification failed` after repointing the alias or changing the host IP, refresh trust once with `ssh -o StrictHostKeyChecking=accept-new sceneverse-prod true`.
- If your ISP/public IP changes, update the Security Group ingress rule for port `22`.
- SQLite data lives on the single host at `/opt/sceneverse-data/sceneverse.db`, so this is acceptable for MVP only.

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
