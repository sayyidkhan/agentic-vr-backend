# AWS Deployment Handoff

This handoff captures the current backend deployment state for the next session.

## Repository

- Backend repo path: `/Users/sayyid/Documents/github-multi/agentic-vr/agentic-vr-backend`
- GitHub repo: `https://github.com/sayyidkhan/agentic-vr-backend`
- Active branch: `main`

## Current Runtime

- Deployment target: AWS EC2
- Region: `us-east-1`
- AMI family: Amazon Linux 2023
- Instance type: `t3.small`
- Runtime model: Docker container built from the repo on the instance
- App port mapping: host `80` -> container `8000`
- Database: private AWS RDS Postgres
- Media storage: S3 bucket with CloudFront playback URLs
- Runtime env file: `/opt/sceneverse-config/shared.env`

Live backend as of `2026-06-10`:

```text
Instance ID: i-0645b2e19351af657
Elastic IP: 18.207.53.115
Public DNS: ec2-18-207-53-115.compute-1.amazonaws.com
Base URL: http://18.207.53.115
Swagger UI: http://18.207.53.115/docs
ReDoc: http://18.207.53.115/redoc
OpenAPI JSON: http://18.207.53.115/openapi.json
RDS instance: sceneverse-postgres
RDS engine: Postgres 18.3
RDS access: private, only from backend EC2 security group
S3 video bucket: sceneverse-videos-647526506319-us-east-1
CloudFront media base: https://d2h4eibmqeyvnj.cloudfront.net
```

Elastic IP change captured in this handoff:

- An Elastic IP was allocated and associated to the EC2 instance after initial deployment.
- Stable public IP: `18.207.53.115`
- This replaced the earlier ephemeral EC2 public IP for both app access and SSH access.

Verified endpoints:

- `GET /`
- `GET /health`
- `GET /health/db`
- `POST /api/scenes/analyze`
- `GET /api/videos`

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

Current deploy path from local machine:

```bash
cd /Users/sayyid/Documents/github-multi/agentic-vr/agentic-vr-backend
./infra/aws/deploy-ec2-with-env.sh
```

This syncs the selected local env values to `/opt/sceneverse-config/shared.env`, rsyncs the repo to EC2, rebuilds the Docker image on the instance, restarts `sceneverse-backend`, and checks `/health` plus `/health/db`.

Post-deploy smoke test:

```bash
curl -fsS http://18.207.53.115/health
curl -fsS http://18.207.53.115/health/db
curl -fsS http://18.207.53.115/
curl -fsS http://18.207.53.115/docs > /dev/null
```

Runtime checks:

```bash
docker ps
docker logs --tail=100 sceneverse-backend
```

## Database And Media

- SQLite to RDS Postgres migration is complete.
- Current DB health should report `postgresql+psycopg`, environment `cloud`, schema revision `20260610_0005`.
- RDS credentials are stored in AWS Secrets Manager under `sceneverse/rds/postgres`.
- Local backend development reaches private RDS through `backend/scripts/run_cloud_backend_local.sh`.
- Video files are stored in S3, and playback URLs use CloudFront.
- Old SQLite files are kept only as fallback/backup and are not the shared source of truth.

## AWS Constraints Observed

This AWS account has had AWS Organizations SCP restrictions that blocked parts of the earlier deploy plan.

Denied actions observed during earlier attempts:

- `ecr:CreateRepository`
- `lambda:CreateFunction`
- `elasticbeanstalk:CreateApplication`
- some EC2 security group creation/ingress operations in earlier regions or sessions

Important nuance:

- Those restrictions blocked the original Lambda / ECR / Beanstalk plan in other attempts and regions.
- A public EC2 deployment did succeed in `us-east-1`.

## AWS Setup Already Done

GitHub OIDC provider was created.

Elastic IP work completed:

- Elastic IP allocated in `us-east-1`
- Elastic IP associated to instance `i-0645b2e19351af657`
- Local SSH alias `sceneverse-prod` repointed to `18.207.53.115`
- Deployment docs and script defaults updated to use the stable endpoint

IAM role:

```text
arn:aws:iam::647526506319:role/sceneverse-backend-github-actions
```

GitHub secret set:

```text
AWS_GITHUB_ACTIONS_ROLE_ARN=arn:aws:iam::647526506319:role/sceneverse-backend-github-actions
```

## Operational Notes

- The current EC2 instance now has an Elastic IP attached, so the public URL is stable.
- The database is now managed by RDS, not host-local SQLite.
- This is currently a single EC2 app host with manual redeploys.

## Recommended Next Step

If real CD is needed next, the most practical path is:

1. protect admin and `/api/db/{table_name}` endpoints
2. upload real playable demo videos
3. attach an EC2 instance role with SSM access
4. add a GitHub Actions deploy workflow that uses OIDC plus `aws ssm send-command`
5. run the same Docker rebuild/restart steps remotely on merge

## Summary

Backend is live on EC2 in `us-east-1` with private RDS Postgres and S3/CloudFront media. CI exists and is working. CD to the EC2 host is still manual. Swagger is available at `http://18.207.53.115/docs`.
