# AWS Deployment Handoff

This handoff captures the current backend deployment state for the next session.

## Repository

- Backend repo path: `/Users/sayyid/Documents/github-multi/agentic-vr/agentic-vr-backend`
- GitHub repo: `https://github.com/sayyidkhan/agentic-vr-backend`
- Active branch during this handoff update: `codex/update-backend-readme-deployment`
- Current checked-in commit at handoff update time: `cb0fb3c`

## Current Runtime

- Deployment target: AWS EC2
- Region: `us-east-1`
- AMI family: Amazon Linux 2023
- Instance type: `t3.small`
- Runtime model: Docker container built from the repo on the instance
- App port mapping: host `80` -> container `8000`
- Persistence: SQLite at `sqlite:///./data/sceneverse.db`

Live backend as of `2026-06-09`:

```text
Instance ID: i-0645b2e19351af657
Public IP: 32.197.15.186
Public DNS: ec2-32-197-15-186.compute-1.amazonaws.com
Base URL: http://32.197.15.186
Swagger UI: http://32.197.15.186/docs
ReDoc: http://32.197.15.186/redoc
OpenAPI JSON: http://32.197.15.186/openapi.json
```

Verified endpoints:

- `GET /`
- `GET /health`
- `POST /api/scenes/analyze`

## CI/CD Reality

- CI is available and active in GitHub Actions.
- CD to the live EC2 backend is manual.
- The Lambda deploy workflow exists, but it is manual-only and separate from the live EC2 runtime.

CI workflow:

```text
.github/workflows/backend-ci.yml
```

What CI does:

- sets up Python 3.13
- installs backend dev dependencies
- runs `python -m compileall app`
- runs `pytest`
- builds the FastAPI Docker image
- builds the Lambda Docker image

Manual deploy workflow file kept in repo:

```text
.github/workflows/deploy-aws-lambda.yml
```

That workflow is not the live deployment path.

## Manual CD Runbook

Current deploy path for the EC2 host:

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

Runtime checks:

```bash
docker ps
docker logs --tail=100 sceneverse-backend
```

## AWS Constraints Observed

This AWS account has had AWS Organizations SCP restrictions that blocked parts of the earlier deploy plan.

Denied actions observed during earlier attempts:

- `ecr:CreateRepository`
- `lambda:CreateFunction`
- `elasticbeanstalk:CreateApplication`
- `ec2:CreateSecurityGroup`
- `ec2:AuthorizeSecurityGroupIngress`

Important nuance:

- Those restrictions blocked the original Lambda / ECR / Beanstalk plan in other attempts and regions.
- A public EC2 deployment did succeed in `us-east-1`.

## AWS Setup Already Done

GitHub OIDC provider was created.

IAM role:

```text
arn:aws:iam::647526506319:role/sceneverse-backend-github-actions
```

GitHub secret set:

```text
AWS_GITHUB_ACTIONS_ROLE_ARN=arn:aws:iam::647526506319:role/sceneverse-backend-github-actions
```

## Operational Notes

- The current EC2 instance uses an ephemeral public IP unless an Elastic IP is attached.
- SQLite is acceptable for MVP/demo use, but it is not durable production storage.
- This is currently a single-host deployment with manual redeploys.

## Recommended Next Step

If real CD is needed next, the most practical path is:

1. attach an EC2 instance role with SSM access
2. ensure SSM agent is running
3. add a GitHub Actions deploy workflow that uses OIDC plus `aws ssm send-command`
4. run the same Docker rebuild/restart steps remotely on merge

## Summary

Backend is live on EC2 in `us-east-1`. CI exists and is working. CD to the EC2 host is still manual. Swagger is available at `http://32.197.15.186/docs`.
