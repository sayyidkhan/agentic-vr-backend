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
| Backend | FastAPI on AWS Lambda or AWS App Runner | Python is strong for agent orchestration and API speed |
| LLM / Vision | OpenAI multimodal model or equivalent vision-capable LLM | Scene parsing needs frame + transcript reasoning |
| Agent Orchestration | Lightweight custom orchestrator first | More demo control than adopting a heavy framework too early |
| External Search | Exa API | Required sponsor-aligned research context |
| Memory | In-memory store for MVP; DynamoDB after demo | Keeps MVP simple while leaving a clean persistence path |
| Frame Storage | Base64 payload for MVP; S3 after demo | Avoid S3 setup until frame persistence matters |
| Payments | Stripe Checkout test mode | Optional premium unlock demo with low implementation burden |
| Deployment | Vercel frontend + AWS backend | Matches PRD and hackathon sponsor alignment |

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
        llm.py
        exa.py
        stripe.py
      store/
        memory.py
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

For demo reliability, ship a local demo video and transcript in `frontend/public`. Do not depend on third-party streaming or copyrighted footage.

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
- Ask the Scene Parser Agent to produce structured scene JSON.
- Initialize scene state in memory.
- Route chat messages through the Orchestrator Agent.
- Return agent traces so the UI can show real coordination.
- Fall back to cached demo scene data if LLM, Exa, or Stripe fails.

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

For MVP, require structured JSON from the model and validate it with Pydantic.

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
- Knowledge boundaries
- Conversation memory
- User question

Hard rule:

Character agents should not use Exa/public research unless that information is plausible in-world knowledge.

### Director Agent

Use the Director Agent for:

- Meta interpretation
- Emotional stakes
- Symbolism
- Continuity checks
- Explaining what characters may be hiding

The Director can use scene context, memory, and summarized Exa research.

### Memory Agent

For MVP, memory can be a Python dictionary keyed by `sceneId`.

Store:

- Scene facts
- Conversation turns
- Compact memory summary
- Current emotional changes

After every chat turn, update the memory summary. Do not store unlimited full conversation history in prompts.

### Research Agent

Use Exa only when the orchestrator detects external context intent.

Examples:

- "Is this based on a real event?"
- "What genre is this scene similar to?"
- "What cinematic references does this remind you of?"

Keep Exa output separate from character knowledge. Feed it mainly to the Director Agent.

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

This is the biggest demo-risk reducer.

### Step 2: Frontend Product Shell

- Video player.
- Pause detection.
- Frame capture.
- Generate button.
- Static mocked scene panel and character cards.

Do this before backend AI integration so the product shape is clear early.

### Step 3: Backend Scene Analysis

- Implement `POST /api/scenes/analyze`.
- Accept frame and transcript.
- Return structured scene JSON.
- If model fails, return cached fallback JSON.

### Step 4: Chat Orchestration

- Implement `POST /api/chat`.
- Route between selected Character Agent and Director Agent.
- Add memory summary.
- Return agent trace.

### Step 5: Exa Research

- Implement Research Agent.
- Add one visible UI path where Exa improves a Director response.
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
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
```

Backend:

```text
OPENAI_API_KEY=
EXA_API_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
FRONTEND_URL=
```

## AWS Deployment Options

### Fastest Reasonable Option

Use AWS App Runner for the FastAPI backend.

Pros:

- Simpler than Lambda packaging for Python dependencies.
- Works well for a normal HTTP API.
- Easier logs and environment variable setup.

Cons:

- Slightly less "serverless-native" than Lambda.

### More Serverless Option

Use AWS Lambda + API Gateway.

Pros:

- Strong sponsor alignment.
- Cheap and scalable.

Cons:

- Packaging, cold starts, and binary dependencies can slow down hackathon execution.

Recommendation:

Use App Runner for speed unless the hackathon heavily rewards Lambda specifically.

## Production Path

After the hackathon:

- Move memory from in-memory store to DynamoDB.
- Store captured frames in S3.
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
| Demo clip causes CORS/frame-capture issues | Host video locally from the frontend `public` folder |
| Backend deployment takes too long | Use App Runner or even one temporary hosted API before optimizing |
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

