# SceneVerse AI Tech Stack

This document reflects the current backend stack after the SQLite to AWS RDS Postgres migration.

## Current Stack

| Layer | Current Choice | Notes |
| --- | --- | --- |
| Frontend | React + TypeScript + Vite | Separate frontend repo. Local default points to the cloud backend. |
| Backend | FastAPI on AWS EC2 | Docker container running on a single EC2 instance. |
| Runtime | Python 3.13 | Root `Dockerfile` and backend venv target Python 3.13. |
| API | FastAPI + Pydantic | OpenAPI docs exposed at `/docs`. |
| ORM | SQLAlchemy 2.x | Shared abstraction for Postgres and local SQLite fallback. |
| Migrations | Alembic | Current schema revision: `20260610_0005`. |
| Cloud database | AWS RDS Postgres | Live shared source of truth. Private, not publicly accessible. |
| Local fallback DB | SQLite | Kept only for isolated local backend experiments and rollback backup. |
| Video metadata | RDS Postgres | `videos` table stores catalogue rows and media pointers. |
| Video files | S3 + CloudFront | Uploads go to S3; playback URLs use CloudFront. |
| AI runtime | Amazon Bedrock | Claude/Kimi model calls are routed through Bedrock where enabled. |
| Enrichment | Exa API | Optional character and research context enrichment. |
| Transcription token flow | OpenAI Realtime transcription token endpoint | Requires server-side OpenAI API key. |
| Payments | Stripe Checkout test mode | Sandbox-ready; production hardening still required. |
| Deployment | Local script over SSH to EC2 | Manual CD via `infra/aws/deploy-ec2-with-env.sh`. |

## Live AWS Runtime

```text
Public API: http://18.207.53.115
EC2 instance: i-0645b2e19351af657
Container: sceneverse-backend
Host port: 80
Container port: 8000
Database: AWS RDS Postgres
Media bucket: sceneverse-videos-647526506319-us-east-1
Media CDN: https://d2h4eibmqeyvnj.cloudfront.net
```

RDS is private. Laptops should not connect directly by opening Postgres to the internet. Local backend development uses an SSH tunnel through the EC2 host.

## Data Flow

```text
Frontend
  -> /backend proxy
  -> FastAPI backend
  -> RDS Postgres for metadata, scenes, characters, memory, sessions
  -> S3 for uploaded video files
  -> CloudFront playback URLs
```

Current shared workflow:

```text
Frontend npm run dev
  -> EC2 backend
  -> RDS Postgres
  -> S3/CloudFront
```

Backend development workflow:

```text
Frontend npm run dev:local
  -> localhost:8000 FastAPI
  -> SSH tunnel 127.0.0.1:15432
  -> private RDS Postgres
  -> S3/CloudFront
```

## Local Backend Development

Use this for normal backend work when you want local code changes but shared cloud data:

```bash
cd agentic-vr-backend/backend
./scripts/run_cloud_backend_local.sh
```

The script:

- fetches the RDS endpoint from AWS
- fetches DB credentials from AWS Secrets Manager
- opens an SSH tunnel through `sceneverse-prod`
- exposes Postgres locally on `127.0.0.1:15432`
- starts FastAPI on `localhost:8000`
- configures `SCENEVERSE_PROFILE=cloud`
- keeps media storage on S3/CloudFront

Then run the frontend against your local backend:

```bash
cd agentic-vr-frontend
npm run dev:local
```

Verify:

```bash
curl http://localhost:8000/health/db
curl http://localhost:5173/backend/health/db
```

Expected DB health:

```text
database: postgresql+psycopg
environment: cloud
schemaRevision: 20260610_0005
```

## Local SQLite Fallback

SQLite files are intentionally kept, but they are no longer the shared source of truth.

Use SQLite only when you want an isolated local backend:

```bash
cd agentic-vr-backend/backend
SCENEVERSE_PROFILE=local uvicorn app.main:app --reload
```

Expected behavior:

```text
local -> SQLite + local media files
cloud -> RDS Postgres + S3/CloudFront media
```

Do not pass `.sqlite` or `.db` files between teammates. Shared development should use RDS.

## Database

Managed tables:

```text
scenes
characters
conversation_turns
research_contexts
character_sessions
videos
alembic_version
```

Current migration status:

```text
SQLite -> RDS Postgres migration complete
Schema revision: 20260610_0005
```

Migrated row counts at cutover:

```text
videos: 2
scenes: 36
characters: 70
conversation_turns: 9
research_contexts: 3
character_sessions: 4
```

## Storage

Video file uploads:

```text
Backend receives upload
  -> stores object in S3 under videos/
  -> returns CloudFront playback URL
  -> stores metadata row in Postgres
```

Current media settings:

```text
MEDIA_STORAGE_BACKEND=s3
S3_VIDEO_BUCKET=sceneverse-videos-647526506319-us-east-1
MEDIA_CDN_BASE_URL=https://d2h4eibmqeyvnj.cloudfront.net
```

The existing two uploaded video rows are smoke-test files and are too small to preview. Upload real MP4/WebM/MOV/M4V/MKV files through the admin page for demo content.

## Backend API Surface

Core product endpoints:

```text
GET  /health
GET  /health/db
POST /api/scenes/analyze
POST /api/chat
POST /api/research
POST /api/checkout
```

Video catalogue/admin endpoints:

```text
GET    /api/videos
GET    /api/videos/{video_id}
POST   /api/videos/link
POST   /api/videos/upload
PATCH  /api/admin/videos/{video_id}
DELETE /api/admin/videos/{video_id}
```

Debug endpoint:

```text
GET /api/db/{table_name}
```

This debug endpoint is useful for hackathon operations but should be protected or removed before production exposure.

## Deployment

Deploy from local machine:

```bash
cd agentic-vr-backend
./infra/aws/deploy-ec2-with-env.sh
```

This:

- syncs selected runtime env values to `/opt/sceneverse-config/shared.env`
- rsyncs the local working tree to EC2
- rebuilds the Docker image on EC2
- restarts `sceneverse-backend`
- verifies `/health` and `/health/db`

The deploy path is still manual. CI exists, but GitHub Actions does not currently redeploy the EC2 host on merge.

## Secrets

Do not commit secrets.

Current secret locations:

```text
RDS credentials: AWS Secrets Manager sceneverse/rds/postgres
Runtime EC2 env: /opt/sceneverse-config/shared.env
Local developer env: backend/.env, gitignored
```

Local backend cloud workflow reads RDS credentials from Secrets Manager and constructs a local tunnel URL. The password should not be copied into tracked docs.

## Current Risks

| Risk | Current State | Next Action |
| --- | --- | --- |
| No auth on admin endpoints | Acceptable for hackathon only | Add auth before production exposure |
| `/api/db/{table}` public debug access | Useful for demo ops, unsafe long term | Protect or remove |
| Manual EC2 deploys | Fast but operator-dependent | Add SSM/GitHub Actions deploy later |
| Smoke videos are invalid media | Catalogue has only tiny test files | Upload real demo videos |
| Single EC2 backend | Simple, not highly available | Containerize behind managed service later |

## Recommended Next Moves

1. Upload real playable demo videos through `/admin/videos`.
2. Add authentication around admin write/delete operations.
3. Protect or remove `/api/db/{table_name}`.
4. Add an automated deploy path using SSM or a container registry.
5. Keep schema changes SQLAlchemy-portable so local SQLite fallback remains cheap.
