#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-southeast-2}"
GITHUB_OWNER="${GITHUB_OWNER:-sayyidkhan}"
GITHUB_REPO="${GITHUB_REPO:-agentic-vr-backend}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
ROLE_NAME="${ROLE_NAME:-sceneverse-backend-github-actions}"
SERVICE_NAME="${SERVICE_NAME:-sceneverse-backend}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-prod}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
FUNCTION_NAME="${SERVICE_NAME}-${ENVIRONMENT_NAME}"

if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  echo "GitHub OIDC provider already exists: $OIDC_ARN"
else
  aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
  echo "Created GitHub OIDC provider: $OIDC_ARN"
fi

TRUST_POLICY="$(mktemp)"
cat > "$TRUST_POLICY" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${OIDC_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/${GITHUB_BRANCH}"
        }
      }
    }
  ]
}
JSON

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document "file://${TRUST_POLICY}"
  echo "Updated role trust policy: $ROLE_ARN"
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://${TRUST_POLICY}" >/dev/null
  echo "Created role: $ROLE_ARN"
fi

DEPLOY_POLICY="$(mktemp)"
cat > "$DEPLOY_POLICY" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaDeploy",
      "Effect": "Allow",
      "Action": [
        "lambda:AddPermission",
        "lambda:CreateFunction",
        "lambda:CreateFunctionUrlConfig",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:GetFunctionUrlConfig",
        "lambda:GetPolicy",
        "lambda:RemovePermission",
        "lambda:TagResource",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:UpdateFunctionUrlConfig"
      ],
      "Resource": "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${SERVICE_NAME}*"
    },
    {
      "Sid": "IamForLambdaExecutionRole",
      "Effect": "Allow",
      "Action": [
        "iam:AttachRolePolicy",
        "iam:CreateRole",
        "iam:GetRole",
        "iam:PassRole",
        "iam:TagRole"
      ],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/${SERVICE_NAME}*"
    }
  ]
}
JSON

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name SceneVerseBackendLambdaDeploy \
  --policy-document "file://${DEPLOY_POLICY}"

echo
echo "Bootstrap complete."
echo "Set this GitHub secret:"
echo "AWS_GITHUB_ACTIONS_ROLE_ARN=${ROLE_ARN}"
echo
echo "GitHub repo: ${GITHUB_OWNER}/${GITHUB_REPO}"
echo "Allowed deploy branch: ${GITHUB_BRANCH}"
echo "AWS region: ${AWS_REGION}"
echo "Lambda function: ${FUNCTION_NAME}"
