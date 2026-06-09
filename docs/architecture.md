# SceneVerse AI Architecture

## Build Stance

Build this as a web-first agentic movie companion. Do not start with VR, multi-video upload, auth, marketplace, or production persistence.

The MVP should prove one loop:

```text
pause video -> capture frame -> analyze scene -> create agents -> chat with memory -> show orchestration
```

## System Architecture

```mermaid
flowchart LR
  User["User / Viewer"]

  subgraph Frontend["Vercel Frontend - React/Vite or Next.js"]
    Video["HTML5 Video Player"]
    Capture["Hidden Canvas Frame Capture"]
    SceneUI["Scene Context Panel"]
    CharacterUI["Character Cards"]
    ChatUI["Chat Interface"]
    TraceUI["Agent Activity Timeline"]
    UnlockUI["Optional Premium Unlock UI"]
  end

  subgraph Backend["AWS Backend - FastAPI on App Runner or Lambda"]
    API["API Layer"]
    SceneParser["Scene Parser Agent"]
    Orchestrator["Orchestrator Agent"]
    CharacterAgents["Character Agents"]
    Director["Director Agent"]
    Memory["Memory Agent"]
    Research["Research Agent"]
    StripeService["Stripe Service"]
    Fallbacks["Cached Demo Fallbacks"]
  end

  subgraph External["External Services"]
    LLM["Vision + Text LLM"]
    Exa["Exa Search API"]
    Stripe["Stripe Checkout"]
  end

  subgraph Storage["MVP Storage"]
    MemoryStore["In-memory Scene Store"]
    DemoAssets["Local Demo Video + Transcript JSON"]
  end

  User --> Video
  Video --> Capture
  DemoAssets --> Video
  DemoAssets --> Capture

  Capture -->|"POST /api/scenes/analyze\nframe + timestamp + transcript"| API
  API --> SceneParser
  SceneParser --> LLM
  SceneParser --> Fallbacks
  SceneParser --> Memory
  Memory --> MemoryStore

  API -->|"scene response"| SceneUI
  API -->|"characters"| CharacterUI

  User --> ChatUI
  ChatUI -->|"POST /api/chat\nsceneId + message + targetAgentId"| API
  API --> Orchestrator
  Orchestrator --> Memory
  Orchestrator --> CharacterAgents
  Orchestrator --> Director
  Orchestrator --> Research
  Research --> Exa
  CharacterAgents --> LLM
  Director --> LLM
  Orchestrator --> Fallbacks
  Orchestrator --> Memory

  API -->|"response + memory summary + agentTrace"| ChatUI
  API -->|"agentTrace"| TraceUI

  UnlockUI -->|"POST /api/checkout"| API
  API --> StripeService
  StripeService --> Stripe
```

## Scene Generation Flow

```mermaid
sequenceDiagram
  actor User
  participant FE as Frontend
  participant API as Backend API
  participant SP as Scene Parser Agent
  participant LLM as Vision/Text LLM
  participant MEM as Memory Agent
  participant Store as Scene Store

  User->>FE: Play demo clip
  User->>FE: Pause at dramatic moment
  FE->>FE: Capture frame with hidden canvas
  FE->>FE: Select transcript segment by timestamp
  FE->>API: POST /api/scenes/analyze
  API->>SP: frame + timestamp + transcript + metadata
  SP->>LLM: Request structured scene JSON
  alt LLM succeeds
    LLM-->>SP: scene facts + character definitions
  else LLM fails or is slow
    SP-->>API: cached fallback scene JSON
  end
  SP->>MEM: initialize scene memory
  MEM->>Store: save scene facts + compact summary
  API-->>FE: sceneId + summary + characters + memorySummary + trace
  FE-->>User: Show scene context, character cards, chat, agent timeline
```

## Chat Orchestration Flow

```mermaid
sequenceDiagram
  actor User
  participant FE as Frontend Chat
  participant API as Backend API
  participant ORCH as Orchestrator Agent
  participant MEM as Memory Agent
  participant CHAR as Character Agent
  participant DIR as Director Agent
  participant RES as Research Agent
  participant EXA as Exa API

  User->>FE: Ask question
  FE->>API: POST /api/chat
  API->>ORCH: sceneId + message + optional targetAgentId
  ORCH->>MEM: load scene facts + memory summary
  MEM-->>ORCH: active scene state

  alt In-world character question
    ORCH->>CHAR: scene facts + character card + boundaries + memory
    CHAR-->>ORCH: in-character response
  else Meta/story question
    ORCH->>DIR: scene facts + memory + user question
    DIR-->>ORCH: director-level explanation
  else External context question
    ORCH->>RES: research query
    RES->>EXA: search
    EXA-->>RES: source summaries
    RES-->>ORCH: public context summary
    ORCH->>DIR: scene facts + memory + research summary
    DIR-->>ORCH: contextual director response
  end

  opt Consistency check needed
    ORCH->>DIR: validate response against scene facts
    DIR-->>ORCH: approved or corrected response
  end

  ORCH->>MEM: store turn + update compact summary
  ORCH-->>API: response + updatedMemorySummary + agentTrace
  API-->>FE: chat response
  FE-->>User: Render response and visible agent trace
```

## API Surface

```mermaid
flowchart TB
  Analyze["POST /api/scenes/analyze"]
  Chat["POST /api/chat"]
  Research["POST /api/research"]
  Checkout["POST /api/checkout"]

  Analyze --> Scene["Scene"]
  Analyze --> Characters["Character[]"]
  Analyze --> MemorySummary["memorySummary"]
  Analyze --> AgentTraceA["agentTrace"]

  Chat --> RespondingAgent["respondingAgent"]
  Chat --> Response["response"]
  Chat --> UpdatedMemory["updatedMemorySummary"]
  Chat --> AgentTraceB["agentTrace"]

  Research --> ResearchSummary["summary"]
  Research --> Sources["sources"]
  Research --> RecommendedContext["recommendedContext"]

  Checkout --> CheckoutUrl["checkoutUrl"]
```

## MVP Build Order

1. Lock one demo clip, transcript JSON, and cached fallback scene JSON.
2. Finish frontend shell: video player, pause detection, frame capture, generate button, context panel, character cards, chat panel, agent trace.
3. Implement `POST /api/scenes/analyze` with structured JSON output and fallback.
4. Implement `POST /api/chat` with orchestrator routing, character/director prompts, memory summary, and `agentTrace`.
5. Add Exa only for one clear Director Agent path.
6. Add Stripe test checkout only after the core demo loop works.

## Key Implementation Choices

- Keep character knowledge separate from Exa/public research.
- Return `agentTrace` from every backend call because visible orchestration is part of the product proof.
- Use in-memory scene state for the hackathon; move to DynamoDB after the demo.
- Keep captured frames as base64 for MVP; move to S3 only if persistence becomes necessary.
- Use App Runner for the FastAPI backend unless Lambda is required by judging criteria.
- Treat VR as a later interface layer, not the foundation of the MVP.
