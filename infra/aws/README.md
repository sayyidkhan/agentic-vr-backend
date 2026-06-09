# AWS CI/CD Setup

This repo uses GitHub Actions OIDC to deploy the backend to AWS Lambda as a Python 3.13 zip package.

## Target

- Runtime: Python 3.13 Lambda zip package
- API exposure: Lambda Function URL
- Deployment: GitHub Actions + direct AWS Lambda create/update
- MVP database: SQLite at `/tmp/sceneverse.db`

SQLite under `/tmp` is demo state only. Move to DynamoDB/RDS, or mount EFS for durable SQLite.

## One-Time AWS Bootstrap

Run this from AWS CloudShell or any terminal with AWS CLI authenticated to the target account:

```bash
cd agentic-vr-backend
AWS_REGION=ap-southeast-2 \
GITHUB_OWNER=sayyidkhan \
GITHUB_REPO=agentic-vr-backend \
GITHUB_BRANCH=main \
bash infra/aws/bootstrap-github-actions.sh
```

The script creates or updates:

- GitHub Actions OIDC provider, if missing
- IAM role for GitHub Actions deploys
- scoped Lambda and IAM permissions for the deploy workflow

Then add this GitHub secret:

```text
AWS_GITHUB_ACTIONS_ROLE_ARN=<printed role arn>
```

Optional GitHub repository variables:

```text
AWS_REGION=ap-southeast-2
SERVICE_NAME=sceneverse-backend
ENVIRONMENT_NAME=prod
FRONTEND_URL=https://your-frontend-url
CORS_ORIGINS=https://your-frontend-url
```

## Deploy

The deployment runs automatically on pushes to `main` that touch backend or infra files. It can also be triggered manually from GitHub Actions:

```text
Deploy Backend to AWS Lambda
```
