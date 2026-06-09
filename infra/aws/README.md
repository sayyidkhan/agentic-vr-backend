# AWS Deployment Notes

## Active Path: Elastic Beanstalk Docker

This AWS account has an AWS Organizations Service Control Policy that explicitly denies Lambda function creation and ECR repository creation for the GitHub Actions deploy role. The practical deployment path for this account is Elastic Beanstalk Docker.

Target:

- Platform: Elastic Beanstalk Docker running on Amazon Linux 2023
- Runtime: `python:3.13-slim` from the root `Dockerfile`
- API exposure: Beanstalk environment URL
- MVP database: SQLite inside the running container
- Health checks: `GET /` and `GET /health`

Recommended environment variables:

```text
APP_NAME=SceneVerse AI Backend
ENVIRONMENT=prod
DATABASE_URL=sqlite:///./data/sceneverse.db
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=*
```

## Optional Path: Lambda Zip

The Lambda workflow and helper scripts are retained for an AWS account where Lambda creation is allowed.

Files:

```text
.github/workflows/deploy-aws-lambda.yml
infra/aws/bootstrap-github-actions.sh
infra/aws/deploy-lambda-zip.sh
infra/aws/lambda-app.yml
```

The Lambda workflow is manual-only in this repo to avoid repeated failures in the current AWS organization.
