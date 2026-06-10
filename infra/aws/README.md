# AWS Deployment Notes

## Active Path: EC2 Docker

This AWS account has had AWS Organizations Service Control Policy restrictions that blocked parts of the Lambda and registry-based deploy path. The practical live deployment path right now is a manually managed EC2 instance running Docker.

Target:

- Platform: EC2 on Amazon Linux 2023 in `us-east-1`
- Runtime: `python:3.13-slim` from the root `Dockerfile`
- API exposure: public EC2 IP / DNS
- Database: private AWS RDS Postgres
- Media: S3 bucket with CloudFront playback URLs
- Health checks: `GET /`, `GET /health`, and `GET /health/db`

Live endpoint as of `2026-06-10`:

```text
Base URL: http://18.207.53.115
Swagger UI: http://18.207.53.115/docs
ReDoc: http://18.207.53.115/redoc
OpenAPI JSON: http://18.207.53.115/openapi.json
```

Elastic IP status:

- An Elastic IP was allocated in `us-east-1` and associated to the live EC2 instance.
- Elastic IP: `18.207.53.115`
- This is now the stable public endpoint used by the app, the deploy script, and the `sceneverse-prod` SSH alias.

Recommended environment variables:

```text
APP_NAME=SceneVerse AI Backend
SCENEVERSE_PROFILE=cloud
ENVIRONMENT=cloud
CLOUD_DATABASE_URL=postgresql+psycopg://sceneverse:<password>@<rds-endpoint>:5432/sceneverse
CLOUD_S3_VIDEO_BUCKET=sceneverse-videos-647526506319-us-east-1
CLOUD_MEDIA_STORAGE_PREFIX=videos
CLOUD_MEDIA_CDN_BASE_URL=https://d2h4eibmqeyvnj.cloudfront.net
YTDLP_COOKIES_FILE=/opt/sceneverse-config/youtube-cookies.txt
YTDLP_USER_AGENT=
YTDLP_POT_PROVIDER_BASE_URL=http://sceneverse-bgutil-provider:4416
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=*
```

Runtime-secret sync:

- The container now reads a persisted host env file at `/opt/sceneverse-config/shared.env`.
- The container mounts `/opt/sceneverse-config` read-only, so runtime files such as `YTDLP_COOKIES_FILE` are visible at the same absolute path inside Docker.
- The deploy script starts a `sceneverse-bgutil-provider` sidecar for YouTube PO-token generation and points the backend at it with `YTDLP_POT_PROVIDER_BASE_URL`.
- Sync your local backend env and deploy code in one step with:

```bash
./infra/aws/deploy-ec2-with-env.sh
```

- If you only want to sync runtime env without redeploying, use:

```bash
ENABLE_LIVE_SCENE_ANALYSIS=true \
ENABLE_EXA_CHARACTER_ENRICHMENT=true \
ENABLE_LIVE_CHARACTER_CHAT=true \
CHARACTER_CHAT_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0 \
./infra/aws/sync-ec2-env.sh
```

- If you only want to redeploy code without resyncing env, use:

```bash
./infra/aws/deploy-ec2-sync.sh
```

## YouTube Download Cookies

YouTube can block anonymous server downloads with the "Sign in to confirm you are not a bot" challenge. For linked YouTube videos, SceneVerse needs a downloaded HTML5-playable copy before the browser can capture scene frames. Configure `YTDLP_COOKIES_FILE` when this happens.

1. Export YouTube cookies from a logged-in browser in Netscape `cookies.txt` format.
2. Install the file on EC2:

```bash
./infra/aws/install-youtube-cookies.sh /path/to/youtube-cookies.txt
```

The script uploads the file to `/opt/sceneverse-config/youtube-cookies.txt`, sets `600` permissions, and updates only the `YTDLP_COOKIES_FILE` line in `/opt/sceneverse-config/shared.env`.

3. If you prefer configuring from local env instead, add this to `backend/.env`:

```env
YTDLP_COOKIES_FILE=/opt/sceneverse-config/youtube-cookies.txt
```

4. Redeploy so Docker mounts `/opt/sceneverse-config` and starts the PO-token provider sidecar:

```bash
./infra/aws/deploy-ec2-sync.sh
```

5. Retry the download endpoint:

```bash
curl -i -X POST http://18.207.53.115/api/admin/videos/<video_id>/download
```

Do not commit the cookies file. Treat it like a session secret and rotate it if downloads start failing again.

## First-Time SSH Setup

The deploy script does not require local AWS CLI access. It does require working SSH access from your machine to the EC2 instance.

Current expected local setup:

- SSH private key: `~/.ssh/sceneverse_ec2`
- SSH host alias: `sceneverse-prod`
- SSH user: `ec2-user`
- Current Elastic IP: `18.207.53.115`

Recommended local SSH config:

```sshconfig
Host sceneverse-prod
  HostName 18.207.53.115
  User ec2-user
  IdentityFile ~/.ssh/sceneverse_ec2
  IdentitiesOnly yes
```

Create the key locally if needed:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/sceneverse_ec2
chmod 600 ~/.ssh/sceneverse_ec2
chmod 644 ~/.ssh/sceneverse_ec2.pub
```

The EC2 instance must also allow SSH:

- Security Group inbound rule: TCP `22`
- Source: your current public IP as `/32`
- Example: `158.140.149.130/32`

Check your current public IP:

```bash
curl https://checkip.amazonaws.com
```

Then update the EC2 Security Group to allow that IP on port `22`.

## If SSH Is Not Bootstrapped Yet

When the instance does not yet trust your local key, you need one bootstrap step.

Practical bootstrap path used here:

1. Open AWS CloudShell or another AWS-authenticated shell.
2. Use EC2 Instance Connect to push a temporary public key for `ec2-user`.
3. SSH into the box using that temporary key.
4. Append your durable local public key from `~/.ssh/sceneverse_ec2.pub` into `~/.ssh/authorized_keys`.
5. Verify direct access with:

```bash
ssh sceneverse-prod
```

Once this is done, normal deploys only need SSH. You do not need to repeat the EC2 Instance Connect step unless you lose key access.

## Does SSH Expire?

Normal SSH access with your durable key does not expire automatically.

That means `ssh sceneverse-prod` keeps working as long as:

- `~/.ssh/sceneverse_ec2` still exists on your machine
- the matching public key is still present in `/home/ec2-user/.ssh/authorized_keys`
- the EC2 Security Group still allows TCP `22` from your current public IP
- the instance is running

What does expire is the temporary EC2 Instance Connect bootstrap access used to get in initially. That temporary key injection is short-lived and should be treated as one-time access, not your normal workflow.

Practical rule:

- EC2 Instance Connect temporary access: expires
- your durable SSH key access: does not expire automatically

## Elastic IP Change Applied

The instance originally came up with an ephemeral public IP. That has now been replaced operationally by an Elastic IP.

What was done:

1. allocated an Elastic IP in `us-east-1`
2. associated it to EC2 instance `i-0645b2e19351af657`
3. updated local SSH config to point `sceneverse-prod` at `18.207.53.115`
4. updated deploy defaults and docs to use the stable URL

Practical result:

- `ssh sceneverse-prod` points at the stable address
- `./infra/aws/deploy-ec2-sync.sh` defaults to the stable public URL
- app smoke tests should use `http://18.207.53.115`

## CI/CD Reality

- CI is automated with GitHub Actions.
- CD to the live EC2 environment is currently local-script driven over SSH.
- There is no GitHub Actions workflow currently redeploying the EC2 host on merge.

Current EC2 env-sync-and-deploy command from your local machine:

```bash
./infra/aws/deploy-ec2-with-env.sh
```

Default assumptions:

- SSH host alias: `sceneverse-prod`
- Public base URL: `http://18.207.53.115`
- Remote app dir: `/opt/sceneverse`
- Remote data dir: `/opt/sceneverse-data`, kept for local media/SQLite fallback only
- Runtime env file: `/opt/sceneverse-config/shared.env`

Example with explicit overrides:

```bash
REMOTE_HOST=ec2-user@18.207.53.115 \
SSH_KEY_PATH="$HOME/.ssh/sceneverse_ec2" \
PUBLIC_BASE_URL=http://18.207.53.115 \
./infra/aws/deploy-ec2-sync.sh
```

What the script does:

- `deploy-ec2-with-env.sh` calls `sync-ec2-env.sh`, then `deploy-ec2-sync.sh`.
- rsyncs the current local repo state to the EC2 instance
- reads runtime secrets from `/opt/sceneverse-config/shared.env`
- rebuilds the Docker image on-instance
- restarts the `sceneverse-backend` container
- smoke tests `GET /health` and `GET /health/db`

Important behavior:

- It deploys your current local working tree, including uncommitted changes.
- It does not run `git pull` on the instance.
- It preserves `/opt/sceneverse-data` for fallback/local files, but the shared DB is RDS Postgres.
- It does not sync secrets automatically from your shell; use `./infra/aws/sync-ec2-env.sh` first when runtime keys change.

Post-deploy smoke test:

```bash
curl -fsS http://18.207.53.115/health
curl -fsS http://18.207.53.115/health/db
curl -fsS http://18.207.53.115/
curl -fsS http://18.207.53.115/docs > /dev/null
```

## Local Backend Against Cloud Database

For backend development with local code but shared cloud data:

```bash
cd backend
./scripts/run_cloud_backend_local.sh
```

This opens:

```text
127.0.0.1:15432 -> sceneverse-postgres RDS endpoint:5432 via sceneverse-prod
```

Then it starts FastAPI on `localhost:8000` with:

```text
SCENEVERSE_PROFILE=cloud
DATABASE_URL=postgresql+psycopg://...@127.0.0.1:15432/sceneverse
MEDIA_STORAGE_BACKEND=s3
```

Do not make the RDS instance public just for local development.

## Things To Watch

- The current instance uses an Elastic IP, so `sceneverse-prod` and the default `PUBLIC_BASE_URL` should stay stable.
- If your local network changes, your public IP changes too. Update the Security Group ingress for port `22`.
- If `ssh sceneverse-prod` fails but port `22` is open, check that `~/.ssh/sceneverse_ec2.pub` is still present in `/home/ec2-user/.ssh/authorized_keys`.
- If SSH fails with `Host key verification failed` after repointing the alias or changing the host IP, refresh trust once with `ssh -o StrictHostKeyChecking=accept-new sceneverse-prod true`.
- If the deploy script fails at the rsync step, SSH is usually the first thing to check.

## Optional Path: Lambda Zip

The Lambda workflow and helper scripts are retained for an AWS account where Lambda creation is allowed.

Files:

```text
.github/workflows/deploy-aws-lambda.yml
infra/aws/bootstrap-github-actions.sh
infra/aws/deploy-lambda-zip.sh
infra/aws/lambda-app.yml
```

The Lambda workflow is manual-only in this repo and is not the current live deployment path.
