# Database Schema

This document describes the current SQLAlchemy-managed schema used by the backend.

Source of truth:

- SQLAlchemy models: [`backend/app/models/db.py`](/Users/sayyid/Documents/github-multi/agentic-vr/agentic-vr-backend/backend/app/models/db.py)
- Alembic migrations: [`backend/alembic/versions/`](/Users/sayyid/Documents/github-multi/agentic-vr/agentic-vr-backend/backend/alembic/versions)

Current schema revision:

- `20260609_0004`

Current managed tables:

- `scenes`
- `characters`
- `conversation_turns`
- `research_contexts`
- `character_sessions`
- `videos`
- `alembic_version`

## Storage Notes

- Current cloud database engine: AWS RDS Postgres via SQLAlchemy and `psycopg`
- Local fallback database engine: SQLite via SQLAlchemy
- Shared team development should use the cloud Postgres database, either through the deployed EC2 backend or through `backend/scripts/run_cloud_backend_local.sh`
- JSON-like payloads are stored as `TEXT` columns with `_json` suffixes
- Timestamps are stored as timezone-aware UTC datetimes

## Entity Relationship Summary

```text
scenes
  ├── characters
  ├── conversation_turns
  ├── character_sessions
  └── research_contexts

videos
```

- One `scene` can have many `characters`
- One `scene` can have many `conversation_turns`
- One `scene` can have many `research_contexts`
- One `scene` can have many `character_sessions`
- `videos` stores catalogue/media metadata and is not currently linked by a foreign key to `scenes.video_id`

## Tables

### `scenes`

Primary purpose:

- Stores the canonical scene snapshot created by `POST /api/scenes/analyze`

Columns:

| Column | Type | Null | Key | Notes |
|---|---|---:|---|---|
| `scene_id` | `String(64)` | No | PK | Scene identifier returned by API |
| `video_id` | `String(128)` | No |  | Source video identifier |
| `timestamp` | `Float` | No |  | Scene timestamp in seconds |
| `frame_ref` | `Text` | Yes |  | Frame reference or inline marker |
| `transcript_segment` | `Text` | Yes |  | Transcript slice associated with scene |
| `summary` | `Text` | No |  | Scene summary |
| `setting` | `Text` | No |  | Setting description |
| `emotional_tone` | `Text` | No |  | Tone summary |
| `conflict` | `Text` | No |  | Core conflict |
| `objects_json` | `Text` | No |  | JSON array of notable objects |
| `director_context` | `Text` | No |  | Director-style interpretation |
| `memory_summary` | `Text` | No |  | Current memory summary for the scene |
| `created_at` | `DateTime(timezone=True)` | No |  | UTC creation timestamp |

### `characters`

Primary purpose:

- Stores character state associated with a scene

Columns:

| Column | Type | Null | Key | Notes |
|---|---|---:|---|---|
| `character_id` | `String(96)` | No | PK | Character identifier |
| `scene_id` | `String` | No | FK | References `scenes.scene_id` |
| `name` | `String(120)` | No |  | Character name |
| `role` | `Text` | No |  | Role in scene |
| `personality` | `Text` | No |  | Personality summary |
| `emotional_state` | `Text` | No |  | Current emotional state |
| `goals_json` | `Text` | No |  | JSON array of goals |
| `knowledge_boundaries_json` | `Text` | No |  | JSON array of knowledge limits |
| `speaking_style` | `Text` | No |  | Style guidance for responses |

Indexes:

- `ix_characters_scene_id` on `scene_id`

### `conversation_turns`

Primary purpose:

- Stores user-to-agent conversational turns after `POST /api/chat`

Columns:

| Column | Type | Null | Key | Notes |
|---|---|---:|---|---|
| `turn_id` | `String(64)` | No | PK | Turn identifier |
| `scene_id` | `String` | No | FK | References `scenes.scene_id` |
| `user_message` | `Text` | No |  | Incoming user prompt |
| `selected_agent` | `String(120)` | No |  | Agent or character name selected |
| `agent_type` | `String(40)` | No |  | Response class, e.g. `character` |
| `agent_response` | `Text` | No |  | Final response text |
| `memory_summary_after_turn` | `Text` | No |  | Updated memory summary after response |
| `agent_trace_json` | `Text` | No |  | JSON array of orchestration/debug steps |
| `created_at` | `DateTime(timezone=True)` | No |  | UTC creation timestamp |

Indexes:

- `ix_conversation_turns_scene_id` on `scene_id`

### `research_contexts`

Primary purpose:

- Stores research lookups associated with a scene

Columns:

| Column | Type | Null | Key | Notes |
|---|---|---:|---|---|
| `research_id` | `String(64)` | No | PK | Research record identifier |
| `scene_id` | `String` | No | FK | References `scenes.scene_id` |
| `query` | `Text` | No |  | Research prompt/query |
| `summary` | `Text` | No |  | Stored research summary |
| `used_by_agent` | `String(120)` | No |  | Defaults to `director` |
| `created_at` | `DateTime(timezone=True)` | No |  | UTC creation timestamp |

Indexes:

- `ix_research_contexts_scene_id` on `scene_id`

### `character_sessions`

Primary purpose:

- Stores lightweight character chat sessions created by `POST /api/character/new`

Columns:

| Column | Type | Null | Key | Notes |
|---|---|---:|---|---|
| `session_id` | `String(64)` | No | PK | Character chat session identifier |
| `scene_id` | `String` | No | FK | References `scenes.scene_id` |
| `character_id` | `String` | No | FK | References `characters.character_id` |
| `created_at` | `DateTime(timezone=True)` | No |  | UTC creation timestamp |

Indexes:

- `ix_character_sessions_scene_id` on `scene_id`
- `ix_character_sessions_character_id` on `character_id`

### `videos`

Primary purpose:

- Stores public catalogue/admin video metadata and media pointers

Columns:

| Column | Type | Null | Key | Notes |
|---|---|---:|---|---|
| `video_id` | `String(64)` | No | PK | Video identifier returned by API |
| `source_type` | `String(32)` | No | Indexed | `upload`, `youtube`, or external source type |
| `title` | `String(255)` | Yes |  | Catalogue title |
| `description` | `Text` | Yes |  | Short catalogue/admin description |
| `original_url` | `Text` | Yes |  | External/YouTube source URL |
| `original_filename` | `String(255)` | Yes |  | Original uploaded filename |
| `storage_backend` | `String(32)` | Yes |  | `s3` or `local` |
| `storage_key` | `Text` | Yes |  | S3 object key or local relative path |
| `playback_url` | `Text` | Yes |  | CloudFront/S3/local playback URL |
| `content_type` | `String(120)` | Yes |  | Uploaded media content type |
| `file_size_bytes` | `Integer` | Yes |  | Uploaded media size |
| `status` | `String(32)` | No |  | Catalogue status, usually `ready` |
| `created_at` | `DateTime(timezone=True)` | No |  | UTC creation timestamp |
| `updated_at` | `DateTime(timezone=True)` | No |  | UTC update timestamp |

Indexes:

- `ix_videos_source_type` on `source_type`

### `alembic_version`

Primary purpose:

- Stores the current migration revision applied to the database

Columns:

| Column | Type | Null | Key | Notes |
|---|---|---:|---|---|
| `version_num` | `VARCHAR(32)` | No | PK | Current Alembic revision |

## API-Level DB Inspection

For debugging without SSH, the backend exposes a read-only table viewer:

### `GET /api/db/{table_name}`

Examples:

```bash
curl 'http://localhost:8000/api/db/scenes?limit=10'
curl 'http://localhost:8000/api/db/characters?limit=10&offset=0'
curl 'http://18.207.53.115/api/db/conversation_turns?limit=5'
```

Supported query params:

- `limit`: default `25`, max `100`
- `offset`: default `0`

Response shape:

```json
{
  "table": "scenes",
  "columns": ["scene_id", "video_id", "timestamp"],
  "limit": 10,
  "offset": 0,
  "rowCount": 5,
  "rows": [
    {
      "scene_id": "scene_123",
      "video_id": "demo-video",
      "timestamp": 42.5
    }
  ]
}
```

Behavior notes:

- Returns `404` for unknown tables
- Orders newest-first when the table has a suitable column like `created_at`
- Parses `_json` columns into structured JSON values in the response
- Intended for debugging and operator visibility

Security note:

- This endpoint currently exposes live table contents over the API
- It is useful for hackathon debugging, but it should be gated or removed before production hardening
