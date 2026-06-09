# SceneVerse AI Tech Stack

## Implementation Bias

Optimize for a reliable 36-hour hackathon demo, not a perfect production system.

The strongest MVP is a controlled web demo with one curated video, one seeded transcript, visible agent orchestration, and enough real AI/tool usage to prove the product thesis:

> A paused video scene can become a believable, interactive agentic world.

Avoid building VR, marketplace, auth, upload flows, or complex persistence until the core pause-to-agent-world loop works.

## Recommended Stack

| Layer | Recommendation | Why |
| --- | --- | --- |
| Frontend | Next.js + React + TypeScript | Fast Vercel deployment, strong UI ergonomics, easy API integration |
| Styling | Tailwind CSS + shadcn/ui | Quick polished UI for panels, cards, tabs, dialogs, buttons |
| Video | Native HTML5 video | Enough for controlled clip playback, pause, timestamp, and frame capture |
| Video Storage | Amazon S3 with presigned upload/download URLs | Simple, durable storage for source videos without keeping large files on EC2 |
| Backend | FastAPI on EC2 | Simple deployment model, fast iteration, and full control during prototyping |
| LLM / Vision | Claude for scene analysis | Strong frame + transcript reasoning for structured scene extraction |
| Agent Orchestration | Amazon Bedrock + lightweight custom orchestrator | Keeps the agentic layer on AWS while preserving demo control |
| Character Data Enrichment | Exa API | Useful for enriching character context with external references |
| Memory / Persistence | SQLite for rapid prototyping; AWS PostgreSQL later | Minimal setup now, cleaner migration path once the product stabilizes |
| Frame Storage | Base64 payload for MVP; S3 for persisted captures later | Keep scene analysis simple now while leaving a path for saved frame assets |
| Payments | Stripe Checkout test mode | Optional premium unlock demo with low implementation burden |
| Deployment | Vercel frontend + EC2 backend | Fastest path to a working demo with AWS-hosted backend control |

## Repo Shape

Suggested structure:

```text
agentic-vr/
  frontend/
    app/
    components/
    lib/
    public/
      demo-video.mp4
      demo-transcript.json
  backend/
    app/
      main.py
      agents/
        scene_parser.py
        orchestrator.py
        character_agent.py
        director_agent.py
        memory_agent.py
        research_agent.py
      models/
        scene.py
        chat.py
      services/
        bedrock.py
        claude_scene_analysis.py
        exa.py
        s3.py
        stripe.py
      store/
        sqlite.py
    requirements.txt
  docs/
    prd.md
  tech-stack.md
```

## Frontend Implementation

Use the first screen as the actual product, not a landing page.

Core UI regions:

- Video player with play, pause, and current timestamp.
- `Generate SceneVerse` button shown after pause.
- Scene context panel showing summary, setting, tone, conflict, and objects.
- Character cards for at least two generated characters.
- Chat panel for selected character or Director Agent.
- Agent activity timeline showing routing and tool usage.
- Optional premium unlock dialog after free interaction limit.

Important implementation detail:

Use a hidden canvas to capture the paused frame from the video:

```ts
const canvas = document.createElement("canvas");
canvas.width = video.videoWidth;
canvas.height = video.videoHeight;
const ctx = canvas.getContext("2d");
ctx?.drawImage(video, 0, 0, canvas.width, canvas.height);
const frameDataUrl = canvas.toDataURL("image/jpeg", 0.82);
```

For demo reliability, you can still ship one local demo video and transcript in `frontend/public`. But if users need uploaded or reusable video assets, store the video files in S3 and stream them into the player using controlled URLs.

## Backend Implementation

Use FastAPI with these endpoints from the PRD:

```text
POST /api/scenes/analyze
POST /api/chat
POST /api/research
POST /api/checkout
```

MVP backend responsibilities:

- Accept captured frame, timestamp, transcript segment, and video metadata.
- Issue presigned S3 URLs for video upload and retrieval when the product moves beyond one local demo clip.
- Ask the Scene Parser Agent to produce structured scene JSON using Claude.
- Persist scene and conversation state in SQLite.
- Route chat messages through the Orchestrator Agent.
- Return agent traces so the UI can show real coordination.
- Fall back to cached demo scene data if Claude, Bedrock, Exa, or Stripe fails.

## Agent Design

Keep the agents as separate modules with explicit inputs and outputs. This makes the demo easier to explain to judges.

### Scene Parser Agent

Input:

- Captured frame
- Timestamp
- Transcript segment
- Video metadata

Output:

- Scene summary
- Setting
- Emotional tone
- Conflict
- Important objects
- Character definitions
- Director context

Use Claude for this step and require structured JSON output validated with Pydantic.

### Orchestrator Agent

Input:

- User message
- Optional target agent
- Scene state
- Memory summary

Routing cases:

- Character perspective question -> selected Character Agent
- Meta/story/cinematic question -> Director Agent
- Trivia/external context question -> Research Agent, then Director Agent

Return an `agentTrace` array:

```json
[
  { "step": "classify_intent", "agent": "orchestrator", "status": "complete" },
  { "step": "load_memory", "agent": "memory", "status": "complete" },
  { "step": "respond", "agent": "maya", "status": "complete" },
  { "step": "update_memory", "agent": "memory", "status": "complete" }
]
```

This trace is important because the judging criteria care about visible agentic coordination.

### Character Agents

Each character should receive:

- Scene facts
- Character card
- Exa-enriched supporting context
- Knowledge boundaries
- Conversation memory
- User question

Hard rule:

Use Exa to enrich the character definition layer before conversation starts, but keep live character responses constrained to plausible in-world knowledge.

### Director Agent

Use the Director Agent for:

- Meta interpretation
- Emotional stakes
- Symbolism
- Continuity checks
- Explaining what characters may be hiding

The Director can use scene context, memory, and summarized Exa research.

### Memory Agent

For MVP, persist memory in SQLite keyed by `sceneId`.

Store:

- Scene facts
- Conversation turns
- Compact memory summary
- Current emotional changes

After every chat turn, update the memory summary. Do not store unlimited full conversation history in prompts.

### Research Agent

Use Exa both for selective character enrichment and for external-context research when the orchestrator detects that intent.

Examples:

- "Is this based on a real event?"
- "What genre is this scene similar to?"
- "What cinematic references does this remind you of?"

Keep raw Exa output separate from character knowledge. For characters, only pass filtered enrichment that fits the world of the scene. For broader analysis, feed Exa output mainly to the Director Agent.

## Data Contracts

Start with these Pydantic models in the backend and mirrored TypeScript types in the frontend.

```ts
type Scene = {
  sceneId: string;
  videoId: string;
  timestamp: number;
  frameRef?: string;
  transcriptSegment?: string;
  summary: string;
  setting: string;
  emotionalTone: string;
  conflict: string;
  objects: string[];
  characters: Character[];
  createdAt: string;
};

type Character = {
  characterId: string;
  sceneId: string;
  name: string;
  role: string;
  personality: string;
  emotionalState: string;
  goals: string[];
  knowledgeBoundaries: string[];
  speakingStyle: string;
};

type ChatResponse = {
  respondingAgent: {
    id: string;
    name: string;
    type: "character" | "director" | "research" | "fallback";
  };
  response: string;
  updatedMemorySummary: string;
  agentTrace: AgentTraceStep[];
};
```

## MVP Build Order

### Step 1: Controlled Demo Assets

- Pick one royalty-free or AI-generated cinematic clip.
- Create a transcript JSON with timestamps.
- Create one cached fallback scene analysis JSON.
- If you want reusable uploaded assets, add an S3 bucket and presigned upload flow early.

This is the biggest demo-risk reducer.

### Step 2: Frontend Product Shell

- Video player.
- Pause detection.
- Frame capture.
- Generate button.
- Static mocked scene panel and character cards.
- If uploads are enabled, add a simple upload flow that stores the source file in S3.

Do this before backend AI integration so the product shape is clear early.

### Step 3: Backend Scene Analysis

- Implement video upload/retrieval endpoints or presigned URL helpers for S3.
- Implement `POST /api/scenes/analyze`.
- Accept frame and transcript.
- Run Claude scene analysis and return structured scene JSON.
- If model fails, return cached fallback JSON.

### Step 4: Chat Orchestration

- Implement `POST /api/chat`.
- Route between selected Character Agent and Director Agent through Bedrock-backed orchestration.
- Read and update SQLite-backed memory summary.
- Return agent trace.

### Step 5: Exa Research

- Implement Research Agent and character enrichment flow.
- Add one visible UI path where Exa improves a Director response or deepens a character card.
- Make failure non-blocking.

### Step 6: Stripe Demo

- Add free interaction counter.
- At limit, show premium unlock.
- Use Stripe Checkout test mode if ready.
- If Stripe setup is unstable, show simulated unlock and explain test-mode path in the pitch.

## Environment Variables

Frontend:

```text
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_S3_VIDEO_BASE_URL=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
```

Backend:

```text
AWS_REGION=
BEDROCK_MODEL_ID=
CLAUDE_SCENE_MODEL_ID=
EXA_API_KEY=
S3_VIDEO_BUCKET=
SQLITE_DB_PATH=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
FRONTEND_URL=
```

## AWS Deployment Options

### Fastest Reasonable Option

Use EC2 for the FastAPI backend and keep SQLite on the instance during prototyping.

Pros:

- Minimal platform complexity during a hackathon or early MVP.
- Easy to run FastAPI, background jobs, and SQLite in one place.
- S3 cleanly offloads large video objects from the EC2 instance.
- Full control over Bedrock integration, caching, and agent orchestration.

Cons:

- More infrastructure to manage than a fully managed runtime.
- SQLite is fine for rapid prototyping, but not the long-term multi-user store.

### Upgrade Path

Move persistence from SQLite to AWS PostgreSQL when concurrent usage, analytics, or multi-tenant data starts to matter.

Pros:

- Better concurrency and durability.
- Cleaner path for relational analytics, user state, and operations.

Cons:

- More setup overhead than SQLite.
- Not necessary until the product proves repeat usage.

Recommendation:

Stay on EC2 + SQLite for speed now. Upgrade to AWS PostgreSQL once prototyping speed is no longer the bottleneck.

## Production Path

After the hackathon:

- Move memory and session state from SQLite to AWS PostgreSQL.
- Keep source videos in S3 and move persisted captured frames there as needed.
- Add creator upload flow.
- Add authentication with Clerk, Auth.js, or Cognito.
- Add persistent scene links.
- Add analytics for interaction depth and conversion.
- Add proper Stripe entitlements.
- Add moderation and copyright-safe content policies.

## Key Technical Risks

| Risk | Mitigation |
| --- | --- |
| Scene analysis latency is too high | Use staged loading and cached fallback scene JSON |
| Agents feel like one chatbot | Show agent trace and use visibly different prompts/roles |
| Character responses leak external knowledge | Separate Character Agent context from Research Agent context |
| Demo clip causes CORS/frame-capture issues | Use one local demo clip first, or serve uploaded videos from a controlled S3/CloudFront path with the correct CORS policy |
| Backend deployment takes too long | Keep the backend on one EC2 service with SQLite before optimizing infrastructure |
| Stripe distracts from core demo | Make Stripe optional and non-blocking |

## Recommended 36-Hour Target

Ship this minimum:

- One controlled video.
- Pause and frame capture.
- Scene analysis with fallback.
- Two character agents.
- One Director Agent.
- Memory-backed follow-up.
- Visible orchestrator trace.
- One Exa-powered Director answer.
- Optional Stripe test unlock.

Do not spend time on VR until this loop is strong.
