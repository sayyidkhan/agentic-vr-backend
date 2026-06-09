# SceneVerse AI Product Requirements Document

## 1. Product Summary

SceneVerse AI is a web-first agentic movie companion that lets a viewer pause a cinematic clip and turn that moment into an interactive movie world.

When the viewer pauses, SceneVerse captures the frame, uses surrounding transcript/context, identifies the scene state, generates character agents, and lets the viewer interact with the scene through a coordinated multi-agent system.

The hackathon version should prove one core claim:

> A paused video scene can become a believable, interactive agentic world.

## 2. Product Positioning

### One-liner

An agentic movie companion that lets viewers pause a scene and step into a living, interactive movie world.

### Tagline

Pause the movie. Step into the world.

### What it is

- A web app for interactive cinematic scene exploration
- A multi-agent system for scene analysis, character simulation, narration, and memory
- A demo of how passive video can become an interactive experience

### What it is not

- Not a generic movie chatbot
- Not primarily a VR app
- Not a full 3D game engine
- Not a streaming platform replacement
- Not dependent on copyrighted movie footage

## 3. Goals

### Hackathon goals

- Build a deployed working demo within 36 hours
- Make the agentic system obvious to judges
- Demonstrate real multi-agent coordination, not a single chatbot wrapper
- Use the sponsor stack meaningfully: AWS, Vercel, Exa, and optionally Stripe
- Create a demo flow that can be shown clearly through a screen recording

### Product goals

- Let a user pause a video and generate an interactive scene context
- Let a user speak to generated character agents
- Let a user ask a Director Agent for story-level explanation
- Preserve conversation continuity through shared memory
- Keep character responses believable through knowledge boundaries

## 4. Non-Goals

For the hackathon MVP, do not build:

- Full VR environment
- Complex 3D scene reconstruction
- User authentication
- Creator upload marketplace
- Multi-video library management
- Long-term persistent user profiles
- Advanced revenue sharing
- Real copyrighted movie integration

## 5. Target Users

### Primary user

A movie, anime, or short-film viewer who wants to explore a scene more deeply by speaking to the characters or asking for story context.

### Secondary users

- Film students analyzing scenes
- Educators using video for discussion
- Creators who want interactive fan experiences
- Streaming platforms looking for engagement features

## 6. Core User Journey

1. User opens SceneVerse.
2. User watches a short cinematic clip.
3. User pauses at a dramatic moment.
4. SceneVerse captures the current frame.
5. SceneVerse analyzes the scene and transcript context.
6. SceneVerse generates scene facts and character cards.
7. User selects a character or Director Agent.
8. User asks a question.
9. Orchestrator routes the question to the right agent.
10. Agent responds using scene context and memory.
11. Memory Agent stores the interaction.
12. User asks a follow-up and receives a coherent response.

## 7. MVP Scope

### Must have

- Web app deployed on Vercel
- Backend API deployed on AWS or equivalent AWS-hosted service
- Video player with a controlled demo clip
- Pause and capture-frame interaction
- Scene analysis from frame plus transcript/context
- Generated character cards
- Chat interface for interacting with character agents
- Director Agent for meta-level scene explanation
- Shared scene memory
- Orchestrator that routes user questions between agents
- Error/fallback states for scene analysis and agent response failure

### Should have

- Exa-powered external context retrieval for movie/scene/actor/trivia enrichment
- Visible agent activity timeline showing what the system is doing
- Stripe payment unlock demo for premium scene exploration
- Screen-recording-ready demo path

### Could have

- Voice input
- Branching "what if" scene exploration
- Multiple saved scenes
- Creator upload flow
- Lightweight immersive/VR viewing mode

## 8. Functional Requirements

### 8.1 Video Experience

The user must be able to:

- Play a demo video
- Pause the video
- See a clear "Generate SceneVerse" action
- Trigger frame capture from the paused moment
- Continue or reset the scene interaction

Acceptance criteria:

- Pausing the video exposes the scene generation action
- Frame capture creates a usable image or scene snapshot reference
- The demo can be repeated reliably without manual developer intervention

### 8.2 Scene Analysis

The system must analyze the paused scene and produce:

- Scene summary
- Visible or inferred characters
- Location/setting
- Emotional tone
- Conflict or tension
- Important objects
- Recommended character agent definitions

Acceptance criteria:

- Scene analysis completes within a demo-friendly time window
- Output is visible to the user as generated scene context or cards
- If transcript/context is missing, the system falls back to visual-only analysis or a pre-seeded scene description

### 8.3 Character Agents

The system must generate character agents with:

- Name
- Role in scene
- Personality
- Current emotional state
- Goals/motivations
- Knowledge boundaries
- Speaking style

Acceptance criteria:

- User can chat with at least two character agents
- Character agents answer from their own perspective
- Character agents do not intentionally reveal information outside their in-world knowledge
- The same follow-up question should use previous conversation context

### 8.4 Director Agent

The Director Agent must:

- Explain the scene at a meta/story level
- Clarify cinematic meaning, emotional stakes, and hidden tension
- Help keep character responses consistent
- Answer questions that should not be answered by an in-world character

Acceptance criteria:

- User can explicitly ask the Director Agent a question
- Orchestrator can route meta-level questions to the Director Agent
- Director responses clearly differ from character-agent responses

### 8.5 Memory Agent

The Memory Agent must:

- Track user questions
- Track agent responses
- Summarize conversation state
- Preserve scene facts
- Detect obvious contradictions where feasible

Acceptance criteria:

- A follow-up question can reference prior conversation
- The system can show or use a compact memory summary
- Resetting a scene clears the active memory state

### 8.6 Research Agent

The Research Agent should:

- Use Exa to retrieve external context when useful
- Separate public/external context from in-world character knowledge
- Provide context to the Director Agent or scene summary

Acceptance criteria:

- Exa usage is visible in the demo or logs
- External context improves at least one Director Agent answer
- If Exa fails, the system continues with local scene context

### 8.7 Orchestrator Agent

The Orchestrator Agent must:

- Decide which agent should answer a user question
- Pass relevant scene context and memory to the selected agent
- Call the Director Agent for consistency checks where needed
- Update memory after each interaction
- Handle failures and fallback routes

Acceptance criteria:

- At least three routing cases work: character question, director/meta question, external-context question
- The UI or logs make agent orchestration understandable to judges
- Failed responses can be retried or safely replaced with fallback output

### 8.8 Stripe Unlock Demo

Stripe integration should demonstrate monetization, even if simulated in test mode.

Possible flow:

1. User receives a limited number of free interactions.
2. User reaches the limit.
3. App prompts for premium scene unlock.
4. User completes Stripe Checkout in test mode.
5. App unlocks more interactions or premium Director insights.

Acceptance criteria:

- Stripe test checkout flow works end-to-end, or a realistic checkout demo is available
- The value proposition is clear: pay to unlock deeper scene interaction
- Payment flow does not block the core demo if Stripe setup fails

## 9. Agent Architecture

### Scene Parser Agent

Purpose: Understand the paused scene.

Inputs:

- Captured frame
- Transcript segment
- Timestamp
- Optional video metadata

Outputs:

- Scene summary
- Character list
- Emotional map
- Conflict map
- Agent setup prompts

### Character Agents

Purpose: Let the user speak to characters inside the story world.

Rules:

- Stay in character
- Respect knowledge boundaries
- Use scene memory
- Avoid revealing external research unless the character would plausibly know it

### Director Agent

Purpose: Maintain story-world consistency and answer meta-level questions.

Responsibilities:

- Explain cinematic meaning
- Clarify emotional stakes
- Validate or correct character responses
- Answer questions about framing, symbolism, or narrative structure

### Memory Agent

Purpose: Preserve continuity across the interactive scene.

Responsibilities:

- Store conversation turns
- Summarize active state
- Track emotional changes
- Identify contradictions

### Research Agent

Purpose: Enrich the scene with live external context.

Responsibilities:

- Retrieve relevant web context through Exa
- Summarize public information
- Feed verified context to the Director Agent
- Keep external context separate from in-world character knowledge

### Orchestrator Agent

Purpose: Coordinate all agents and route work.

Responsibilities:

- Classify user intent
- Select responding agent
- Inject relevant memory/context
- Trigger research when needed
- Store final output in memory
- Apply fallback handling

## 10. System Flow

1. User pauses video.
2. Frontend captures current frame and timestamp.
3. Frontend sends frame, timestamp, transcript segment, and video metadata to backend.
4. Scene Parser Agent generates scene context.
5. Backend initializes character agents, Director Agent, Memory Agent, and Orchestrator state.
6. Frontend displays character cards and chat panel.
7. User sends a question.
8. Orchestrator classifies intent.
9. Orchestrator routes to Character Agent, Director Agent, or Research Agent.
10. Selected agent responds.
11. Director Agent validates consistency when needed.
12. Memory Agent stores the interaction.
13. Frontend displays response and updated memory/activity.

## 11. Suggested Technical Architecture

### Frontend

- Vercel-hosted web app
- Video player
- Scene generation button
- Character cards
- Chat interface
- Agent activity timeline
- Optional premium unlock prompt

### Backend

- AWS-hosted API
- Agent orchestration service
- Scene analysis service
- Memory/session store
- Exa integration
- Stripe webhook/checkout handler if implemented

### Data storage

Minimum viable storage:

- In-memory session state for demo
- JSON scene context per session
- Conversation memory per session

Better version:

- DynamoDB or another AWS database for scene/session memory
- S3 for captured frames

## 12. Data Model

### Scene

- `sceneId`
- `videoId`
- `timestamp`
- `frameUrl` or `frameData`
- `transcriptSegment`
- `summary`
- `setting`
- `emotionalTone`
- `conflict`
- `objects`
- `characters`
- `createdAt`

### Character

- `characterId`
- `sceneId`
- `name`
- `role`
- `personality`
- `emotionalState`
- `goals`
- `knowledgeBoundaries`
- `speakingStyle`

### ConversationTurn

- `turnId`
- `sceneId`
- `userMessage`
- `selectedAgent`
- `agentType`
- `agentResponse`
- `memorySummaryAfterTurn`
- `createdAt`

### ResearchContext

- `researchId`
- `sceneId`
- `query`
- `sourceSummaries`
- `usedByAgent`
- `createdAt`

## 13. API Requirements

### `POST /api/scenes/analyze`

Purpose: Create scene context from a paused frame.

Request:

- `frame`
- `timestamp`
- `transcriptSegment`
- `videoMetadata`

Response:

- `sceneId`
- `sceneSummary`
- `characters`
- `directorContext`
- `memorySummary`

### `POST /api/chat`

Purpose: Send a user message into the scene agent system.

Request:

- `sceneId`
- `message`
- `targetAgentId` optional

Response:

- `respondingAgent`
- `response`
- `updatedMemorySummary`
- `agentTrace`

### `POST /api/research`

Purpose: Retrieve external context through Exa.

Request:

- `sceneId`
- `query`

Response:

- `summary`
- `sources`
- `recommendedContext`

### `POST /api/checkout`

Purpose: Start Stripe Checkout for premium unlock.

Request:

- `sceneId`
- `unlockType`

Response:

- `checkoutUrl`

## 14. UX Requirements

### Primary screen

The first screen should be the working product, not a marketing landing page.

Required areas:

- Video player
- Pause/generate control
- Scene context panel
- Character cards
- Chat panel
- Agent activity or routing trace

### Interaction principles

- Make the agentic work visible
- Keep the demo path simple
- Do not overwhelm users with too many agents
- Prioritize fast comprehension over feature density
- Use a controlled cinematic clip to reduce demo risk

## 15. Failure Handling

### Wrong character detected

- Allow user to rename character
- Allow user to remove character
- Allow character regeneration

### Transcript missing

- Use visual-only analysis
- Use fallback seeded scene description
- Ask user for optional context

### Agent gives out-of-character response

- Director Agent flags inconsistency
- Regenerate response with stricter constraints

### Exa search fails

- Continue with local scene context
- Mark external context unavailable

### Stripe fails

- Continue core demo
- Show fallback premium-unlock simulation

### Backend latency

- Show staged progress: analyzing frame, creating agents, initializing memory
- Use cached demo output if needed for presentation reliability

## 16. Success Metrics

### Hackathon success metrics

- Working deployed app
- Scene generation completes successfully in demo
- At least two character agents are generated
- User can chat with a character agent
- User can ask Director Agent for deeper context
- Follow-up question uses memory
- Exa usage is visible or explainable
- Stripe integration is functional or clearly demoed in test mode

### Product success metrics

- Time from pause to interactive scene
- Number of meaningful user-agent turns per scene
- User satisfaction with character believability
- Repeat scene exploration rate
- Premium unlock conversion rate

## 17. Demo Script

1. Open SceneVerse.
2. Play a short cinematic clip.
3. Pause at a tense moment.
4. Click "Generate SceneVerse."
5. Show scene analysis and generated character cards.
6. Ask one character: "What are you feeling right now?"
7. Ask a follow-up that depends on memory.
8. Ask the Director Agent: "What is really happening in this scene?"
9. Trigger Exa-powered context retrieval if relevant.
10. Show optional Stripe premium unlock for deeper exploration.
11. End with the positioning: "We turn passive video into interactive cinematic worlds."

## 18. Judging Alignment

### Agent overview

SceneVerse uses specialized agents for scene parsing, character simulation, narration, research, memory, and orchestration.

### Autonomy and decision-making

The Orchestrator Agent classifies user intent, selects the correct agent, decides when research is needed, and updates memory after each turn.

### Actions and tool use

Agents analyze frames, retrieve external context through Exa, manage memory, and optionally trigger Stripe payment unlocks.

### Orchestration

The Orchestrator Agent coordinates multiple agents and keeps responses coherent through Director Agent validation and Memory Agent state.

### Human-in-the-loop

The user chooses when to pause, who to talk to, when to ask the Director Agent, and whether to approve or correct generated character cards.

### Failure handling

The system has fallbacks for missing transcript, wrong character detection, search failure, payment failure, and inconsistent agent responses.

### Demo and presentation

The demo is designed as a clear end-to-end screen recording with a controlled clip and repeatable outputs.

## 19. Roadmap

### Phase 1: Hackathon MVP

- Controlled video demo
- Pause-to-scene generation
- Character cards
- Character chat
- Director Agent
- Memory
- Exa context
- Deployed app

### Phase 2: Post-hackathon prototype

- Creator upload flow
- Better transcript ingestion
- Persistent scene sessions
- More robust character correction
- Stripe pay-per-scene unlock
- Shareable interactive scene links

### Phase 3: Commercial product

- Creator monetization
- Education packages
- Streaming platform integrations
- Premium fan experiences
- Analytics for creators
- Multi-scene story memory

## 20. Key Risks

### Risk: Too broad for 36 hours

Mitigation: Build a controlled demo around one high-quality cinematic clip and one strong scene.

### Risk: Agents feel like generic chatbots

Mitigation: Make agent roles, routing, memory, and knowledge boundaries visible in the UI and pitch.

### Risk: Scene analysis is unreliable

Mitigation: Use a curated clip, transcript segment, and fallback seeded scene context.

### Risk: VR distracts from core value

Mitigation: Treat VR as optional. The product is the agentic movie world, not the interface.

### Risk: Copyright issues

Mitigation: Use original, royalty-free, AI-generated, or public domain footage.

## 21. Open Decisions

- Which exact demo clip will be used?
- Which LLM/vision model will power scene analysis?
- Will backend use AWS Lambda, ECS, or another AWS service?
- Will captured frames be stored in S3 or kept ephemeral?
- Is Stripe a real test-mode checkout or a simulated unlock for demo safety?
- How much of the agent trace should be exposed in the UI?

## 22. Recommended 36-Hour Build Plan

### First 6 hours

- Lock demo clip and transcript
- Scaffold frontend and backend
- Define scene/context JSON schema
- Build video player and pause capture

### Hours 6-18

- Implement scene analysis endpoint
- Implement character card generation
- Build chat UI
- Implement basic orchestrator
- Add memory state

### Hours 18-28

- Add Director Agent
- Add Exa Research Agent
- Add visible agent trace
- Deploy frontend and backend

### Hours 28-34

- Add Stripe test unlock if feasible
- Polish UI and demo flow
- Add fallback cached scene context
- Record demo

### Final 2 hours

- Prepare submission links
- Finalize slides
- Test deployed app
- Rehearse pitch
