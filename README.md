# AI-Powered Two-Way Calling Agent

[![Tests](https://img.shields.io/badge/tests-102%20passed-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An autonomous, full-stack outbound sales qualification system for commercial and industrial Reverse Osmosis (RO) water treatment plants (SERP Hawk). The system conducts natural, two-way conversational voice calls, extracts 9 critical qualification slots in real time, steers conversations using a deterministic finite-state planner paired with Google Gemini 2.5 Flash, records audit events, generates post-call summaries, and visualizes call telemetry on a Next.js admin dashboard.

---

## Demo & Screenshots

<!-- Replace DEMO_VIDEO_ID with your YouTube / Loom video ID -->
[![Watch Demo Video](https://img.youtube.com/vi/DEMO_VIDEO_ID/maxresdefault.jpg)](https://youtube.com/watch?v=DEMO_VIDEO_ID)

| Admin Dashboard | Live Call Interface |
| :---: | :---: |
| ![Dashboard Screenshot](https://raw.githubusercontent.com/<YOUR_GITHUB_USERNAME>/AI-Powered-Two-Way-Calling-Agent/main/docs/dashboard.png) | ![Live Call Screenshot](https://raw.githubusercontent.com/<YOUR_GITHUB_USERNAME>/AI-Powered-Two-Way-Calling-Agent/main/docs/live-call.png) |

---

## 1. Overview

The **AI-Powered Two-Way Calling Agent** solves high-volume outbound lead qualification for commercial equipment sales. When an admin initiates a call to a prospect:
1. The agent delivers an opening greeting tailored to the prospect and product.
2. The browser captures customer audio using the **Web Speech API** (`webkitSpeechRecognition`), streaming transcribed text over an authenticated **WebSocket** connection.
3. The backend orchestrates a multi-phase conversation pipeline:
   - **Perceives** customer utterances, tracks silence intervals, and detects customer interruptions (barge-in).
   - **Extracts** structured slot values (capacity, location, budget, timeline, application, etc.) using hybrid heuristic and regex parsers.
   - **Plans** the next conversational move via a deterministic finite-state machine (FSM) ensuring all mandatory slots are gathered without hallucination or topic drift.
   - **Responds** using **Google Gemini 2.5 Flash** to craft polite, concise, voice-friendly conversational turns (with automatic rule-based fallback).
   - **Persists** every turn, intermediate slot state, and lifecycle audit event into **PostgreSQL**.
4. The frontend synthesizes the agent's reply via browser **SpeechSynthesis** (Text-to-Speech) with barge-in interruption detection.
5. Upon call conclusion or disconnect, the system generates an executive summary, detects lead sentiment (`hot`, `warm`, `cold`, `not_interested`), flags follow-up requirements, and mirrors call metrics to the **Next.js** admin portal.

---

## 2. Models and Tools Used

| Component | Technology | Rationale / Implementation |
| :--- | :--- | :--- |
| **LLM Reasoning & Phrasing** | **Google Gemini 2.5 Flash** | Used for natural conversational reply phrasing (`app/agent/dialogue.py`) and post-call structured JSON extraction & summary (`app/agent/summary.py`). Super-fast latency (<500ms) suitable for voice conversations. |
| **Speech-to-Text (STT)** | **Browser Web Speech API (`webkitSpeechRecognition`)** | Zero-latency, browser-native client-side transcription streaming continuous speech events with confidence scores. Handles intermittent background noise and error recovery. |
| **Text-to-Speech (TTS)** | **Browser `window.speechSynthesis`** | Real-time speech generation with garbage-collection protection (`utteranceRef`), natural voice selection, and instant cancellation on customer barge-in. |
| **Voice / Transport Layer** | **FastAPI WebSockets (`/ws/call/{call_id}`)** | Low-latency duplex streaming of text, turns, state updates, barge-in interrupts, and error events protected with JWT query-param authentication. |
| **Telephony Interface** | **Pluggable Provider Architecture (`CallProvider`)** | Includes a full `BrowserCallProvider` for browser test calls and a pre-configured `TwilioCallProvider` ready for Twilio Media Streams (mocked in demo due to trial account restrictions on unverified numbers). |
| **Backend Framework** | **FastAPI + Async SQLAlchemy 2.0** | Async I/O, strict Pydantic v2 validation, non-blocking authentication via `asyncio.to_thread` for bcrypt, and connection pooling. |
| **Frontend Framework** | **Next.js 15 (App Router) + React 19** | Fast, responsive admin UI with dark mode, live status updates, reactive filters, and custom CSS design system. |
| **Database** | **PostgreSQL 16** | Robust relational persistence with foreign keys, JSONB fields, automated Alembic migrations, and ACID event tracking. |

---

## 3. Architecture Diagram

```mermaid
graph TB
    subgraph Client["Frontend Client (Next.js 15 / Chrome)"]
        UI["Admin Dashboard & Live Call UI"]
        STT["Web Speech Recognition (STT)"]
        TTS["SpeechSynthesis (TTS)"]
        WSClient["WebSocket Client (?token=JWT)"]
    end

    subgraph Gateway["API & Communication Gateway (FastAPI)"]
        AuthMid["JWT Auth Guard"]
        REST["REST Routes (/auth, /contacts, /calls, /dashboard, /health)"]
        WSRoute["WebSocket Handler (/ws/call/{id})"]
        SessionMgr["CallSession (Lock & Lifecycle)"]
    end

    subgraph AgentEngine["Conversational Agent Engine"]
        FSM["Deterministic Planner (FSM)"]
        Extractor["Slot Extractor (Regex + Heuristics)"]
        LLMClient["Gemini 2.5 Flash Client"]
        Fallback["Rule-Based Fallback Generator"]
        SummaryEngine["Summary & Sentiment Engine"]
    end

    subgraph Storage["Persistence Layer (PostgreSQL)"]
        DB[(PostgreSQL 16)]
        T_Calls["calls"]
        T_Turns["call_turns"]
        T_Extracted["call_extracted_data"]
        T_Summary["call_summaries"]
        T_Events["call_events"]
        T_Contacts["contacts"]
        T_Admins["admins"]
    end

    UI -->|REST + Bearer Token| REST
    WSClient <-->|Duplex Frames| WSRoute
    STT -->|Speech Events| WSClient
    WSClient -->|Speak Utterance| TTS

    REST --> AuthMid
    WSRoute --> AuthMid
    WSRoute --> SessionMgr
    SessionMgr --> FSM
    SessionMgr --> Extractor
    FSM --> LLMClient
    LLMClient -.->|On Timeout / Error| Fallback
    SessionMgr --> SummaryEngine
    SummaryEngine --> LLMClient

    REST --> DB
    SessionMgr --> DB
    DB --- T_Calls
    DB --- T_Turns
    DB --- T_Extracted
    DB --- T_Summary
    DB --- T_Events
    DB --- T_Contacts
    DB --- T_Admins
```

---

## 4. AI Workflow

The conversational intelligence operates as a **Perceive-Extract-Plan-Respond-Persist-Summarize** state machine:

```mermaid
flowchart TD
    A[Customer Speech Received] --> B[Perceive: Update Silence Timers & Barge-in Monitor]
    B --> C[Extract: Hybrid Regex & Value Normalization]
    C --> D{Evaluate Slots: 9 Sales Attributes}
    D --> E[Plan: Transition FSM Phase GATHERING -> CONFIRMING -> WRAP_UP]
    E --> F{Gemini LLM Available?}
    F -- Yes --> G[Generate Contextual Phrasing with Gemini Flash]
    F -- No / Error --> H[Select Deterministic Template from Rule Engine]
    G --> I[Format Voice-Friendly Output Sentence]
    H --> I
    I --> J[Persist: Commit Turns & Intermediate Slots to PostgreSQL]
    J --> K[Emit Agent Reply Frame to WebSocket]
    K --> L{Call Concluded?}
    L -- Yes --> M[Summarize: Generate JSON Summary, Intent, Lead Status & Events]
    L -- No --> N[Await Next Utterance or Silence Interval]
    M --> O[Mark Call Completed & Persist Final Metrics]
```

### The 9 Qualification Slots
1. `customer_name`: Contact or caller identity
2. `company_name`: Business or firm name
3. `requirement`: Core product requirement (e.g., Commercial RO Plant)
4. `application`: Industry use case (e.g., Hotel, Hospital, Manufacturing)
5. `ro_capacity_lph`: Volume requirement (e.g., 500 LPH, 1000 LPH)
6. `location`: Installation city / state (e.g., Bangalore, Pune)
7. `budget`: Financial expectation (e.g., ₹2,50,000, 1 Lakh)
8. `timeline`: Target installation schedule (e.g., Immediate, 1 month)
9. `additional_requirements`: Pre-treatment, water test reports, TDS levels

---

## 5. Calling Workflow

Sequence of interactions during a live browser-based sales call:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Sales Admin
    participant UI as Next.js Admin UI
    participant API as FastAPI REST
    participant WS as FastAPI WebSocket
    participant Session as CallSession Lock
    participant Agent as DialogueAgent & Extractor
    participant LLM as Gemini Flash
    participant DB as PostgreSQL
    participant TTS as Browser SpeechSynthesis

    Admin->>UI: Click "Start Call" on Contact row
    UI->>API: POST /calls {"contact_id": 1}
    API->>DB: INSERT into calls (status='queued')
    API-->>UI: 201 Created {id: "call-uuid"}
    UI->>UI: Navigate to /live-call/{id}
    UI->>WS: Connect ws://localhost:8000/ws/call/{id}?token={jwt}
    WS->>WS: Verify JWT Query Param
    WS->>Session: Initialize CallSession & acquire Lock
    Session->>DB: UPDATE calls (status='in_progress', start_time=now)
    Session->>DB: INSERT call_events (event_type='call_started')
    Session->>WS: Send {"type": "agent_reply", "text": "Opening greeting..."}
    WS-->>UI: Agent greeting frame
    UI->>TTS: Speak greeting aloud via SpeechSynthesis
    
    rect rgb(240, 248, 255)
    Note over UI,WS: Continuous Two-Way Speech Loop
    Admin->>UI: Customer speaks: "We need 500 LPH RO for our hotel in Bangalore"
    UI->>WS: Send {"type": "customer_speech", "text": "...", "confidence": 0.95}
    WS->>Session: on_customer_speech(text)
    Session->>Agent: handle(text) -> Extract slots & plan next question
    Agent->>LLM: Formulate conversational response
    LLM-->>Agent: "Got it, 500 LPH for a hotel. What budget do you have in mind?"
    Agent-->>Session: Turn reply + state
    Session->>DB: Save turns, upsert extracted slots
    Session->>WS: Send {"type": "agent_reply", "text": "..."}
    Session->>WS: Send {"type": "state_update", "slots": {...}}
    WS-->>UI: Receive reply & state
    UI->>TTS: Speak agent reply aloud
    end

    opt Customer Interrupts (Barge-in)
        Admin->>UI: Customer speaks while TTS is playing
        UI->>TTS: cancel()
        UI->>WS: Send {"type": "interrupt"}
        WS->>DB: INSERT call_events (event_type='interrupted')
    end

    Admin->>UI: Click "End Call" (or wrap-up reached)
    UI->>WS: Send {"type": "end_call"}
    WS->>Session: finish("completed")
    Session->>DB: UPDATE calls (status='completed', duration)
    Session->>Agent: generate_summary()
    Agent->>LLM: Generate structured JSON summary
    LLM-->>Agent: {summary, intent, outcome, lead_status, followup}
    Session->>DB: INSERT call_summaries & call_events ('call_ended')
    Session->>WS: Send {"type": "call_status", "status": "completed"}
    WS-->>UI: Close connection
    UI->>UI: Redirect to /calls/{id} details page
```

---

## 6. Setup Steps (1 to 8)

### Prerequisites
- Python 3.11+
- Node.js 18+ (Node 20+ recommended)
- PostgreSQL 15+ (local service or Docker)
- Google Chrome (required for Web Speech API)

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/AI-Powered-Two-Way-Calling-Agent.git
cd AI-Powered-Two-Way-Calling-Agent
```

### Step 2: Environment Configuration
Copy `.env.example` to both the root and `backend/` directory:
```bash
cp .env.example .env
cp .env.example backend/.env
```
Update `backend/.env` with your Google Gemini API key:
```ini
# backend/.env
DATABASE_URL=postgresql+asyncpg://calling_agent:secret@localhost:5432/calling_agent_db
SECRET_KEY=change-me-to-a-random-32-char-string-in-production
GEMINI_API_KEY=your_actual_gemini_api_key_here
ADMIN_EMAIL=admin@sephawk.com
ADMIN_PASSWORD=Admin@123
CALL_PROVIDER=browser
STT_PROVIDER=browser
TTS_PROVIDER=browser
```

### Step 3: Run PostgreSQL
#### Option A: Docker Compose
```bash
docker compose up -d
```
#### Option B: Local PostgreSQL Service
Create the dev and test databases:
```sql
CREATE USER calling_agent WITH PASSWORD 'secret';
CREATE DATABASE calling_agent_db OWNER calling_agent;
CREATE DATABASE calling_agent_test OWNER calling_agent;
```

### Step 4: Install Backend Dependencies & Run Migrations
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
```

### Step 5: Seed Database with Initial Admin & Contacts
```bash
# From the backend directory with venv activated:
python scripts/seed_db.py
```
This initializes:
- Admin user: `admin@sephawk.com` (password from `ADMIN_PASSWORD` in `.env`)
- Sample contacts: Rahul Kumar (Hotel Blue Diamond) & Priya Sharma (Sharma Food Industries).

### Step 6: Start the FastAPI Backend
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend API and Swagger docs will be accessible at `http://localhost:8000/docs`.

### Step 7: Install Frontend Dependencies & Start Next.js
Open a new terminal:
```bash
cd frontend
npm install
npm run dev
```
The Next.js dashboard will be live at `http://localhost:3000`.

### Step 8: Start a Test Call in Google Chrome
1. Open **Google Chrome** and navigate to `http://localhost:3000`.
2. Login with the seeded admin credentials:
   - **Email:** `admin@sephawk.com`
   - **Password:** The password configured in `ADMIN_PASSWORD` in your `.env` (defaults to `Admin@123`).
3. Navigate to **Contacts** (`/contacts`) and click **"Start Call"** on any contact.
4. Allow Chrome microphone permissions when prompted.
5. Speak naturally into your microphone (e.g., *"I need a 500 LPH RO plant for my hotel in Bangalore with a budget of 1 lakh within 1 month. My name is Rahul Kumar"*).
6. Click **"End Call"** and review the real-time transcript, the 9 extracted slots, the AI executive summary, and the audit events on `/calls/[id]`.

---

## 7. API Reference

All backend routes are mounted without an `/api/v1` prefix.

| Method | Endpoint | Description | Auth Required | Request / Query Parameters |
| :--- | :--- | :--- | :---: | :--- |
| `POST` | `/auth/login` | Exchange admin credentials for a JWT access token | No | JSON: `email`, `password` |
| `GET` | `/auth/me` | Fetch authenticated admin identity | Yes (Bearer) | Header: `Authorization: Bearer <token>` |
| `GET` | `/dashboard/stats` | Aggregated call metrics & KPI counters | Yes (Bearer) | None |
| `GET` | `/contacts` | List contacts with optional search & pagination | Yes (Bearer) | Query: `search`, `limit`, `offset` |
| `POST` | `/contacts` | Create a new validated sales contact | Yes (Bearer) | JSON: `name`, `phone_e164`, `company`, `purpose`, `product` |
| `GET` | `/contacts/{contact_id}` | Retrieve contact details by ID | Yes (Bearer) | Path: `contact_id` (integer) |
| `GET` | `/calls` | Filtered, paginated list of calls | Yes (Bearer) | Query: `status`, `lead_status`, `outcome`, `customer`, `date_from`, `date_to`, `page`, `page_size` |
| `POST` | `/calls` | Queue a new outbound call | Yes (Bearer) | JSON: `contact_id` (int) or `phone_number` (E.164) |
| `GET` | `/calls/{call_id}` | Full call dossier (turns, slots, summary, events) | Yes (Bearer) | Path: `call_id` (UUID) |
| `GET` | `/health` | Liveness check & service status | No | None |
| `WS` | `/ws/call/{call_id}` | Live bidirectional audio & speech event stream | Yes (Query) | Query: `?token=<jwt_access_token>` |

---

## 8. WebSocket Protocol Specification

The `/ws/call/{call_id}?token={token}` endpoint powers the live interactive call session:

### Client -> Server Messages
| Type | Payload Schema | Description |
| :--- | :--- | :--- |
| `customer_speech` | `{"type": "customer_speech", "text": string, "confidence": float \| null}` | Customer transcribed utterance from Web Speech STT |
| `interrupt` | `{"type": "interrupt"}` | Barge-in signal sent when customer speaks during agent TTS |
| `end_call` | `{"type": "end_call"}` | Explicit termination signal when user clicks "End Call" |
| `stt_failure` | `{"type": "stt_failure", "detail": object}` | Diagnostic error event emitted from `recognition.onerror` |

### Server -> Client Messages
| Type | Payload Schema | Description |
| :--- | :--- | :--- |
| `agent_reply` | `{"type": "agent_reply", "text": string, "turn_index": int}` | Formulated conversational reply for client TTS synthesis |
| `state_update` | `{"type": "state_update", "slots": object, "phase": string, "pending_slot": string \| null}` | Real-time state of 9 qualification slots and FSM phase |
| `call_status` | `{"type": "call_status", "status": string, "reason": string, "duration_seconds": int \| null}` | Terminal or updated call state (`completed`, `disconnected`, etc.) |
| `error` | `{"type": "error", "detail": string}` | Protocol error notification |

---

## 9. Database Schema and ERD

```mermaid
erDiagram
    ADMINS ||--o{ CALLS : creates
    CONTACTS ||--o{ CALLS : receives
    CALLS ||--o{ CALL_TURNS : contains
    CALLS ||--o| CALL_EXTRACTED_DATA : extracts
    CALLS ||--o| CALL_SUMMARIES : summarizes
    CALLS ||--o{ CALL_EVENTS : logs

    ADMINS {
        integer id PK
        varchar email UK
        varchar password_hash
        timestamp created_at
    }

    CONTACTS {
        integer id PK
        varchar name
        varchar phone_e164
        varchar company
        text purpose
        varchar product
        timestamp created_at
    }

    CALLS {
        uuid id PK
        integer contact_id FK
        varchar phone_number
        enum direction
        enum provider
        varchar provider_call_sid
        enum status
        enum outcome
        enum lead_status
        boolean followup_required
        timestamp start_time
        timestamp end_time
        integer duration_seconds
        timestamp created_at
    }

    CALL_TURNS {
        integer id PK
        uuid call_id FK
        integer turn_index
        enum speaker
        text message
        float confidence
        timestamp created_at
    }

    CALL_EXTRACTED_DATA {
        uuid call_id PK, FK
        varchar customer_name
        varchar company_name
        varchar requirement
        varchar ro_capacity_lph
        varchar location
        varchar application
        varchar budget
        varchar timeline
        varchar additional_requirements
        jsonb raw_json
        timestamp updated_at
    }

    CALL_SUMMARIES {
        uuid call_id PK, FK
        text summary
        jsonb key_requirements
        text customer_intent
        jsonb important_points
        jsonb followup_actions
        enum outcome
        enum lead_status
        boolean followup_required
        timestamp created_at
    }

    CALL_EVENTS {
        integer id PK
        uuid call_id FK
        varchar event_type
        jsonb detail
        timestamp created_at
    }
```

### Enumerations
- **`CallStatus`**: `queued`, `ringing`, `in_progress`, `completed`, `no_answer`, `failed`, `disconnected`, `invalid_number`
- **`CallOutcome`**: `interested`, `not_interested`, `callback_requested`, `no_response`, `failed`, `incomplete`
- **`LeadStatus`**: `hot`, `warm`, `cold`, `interested`, `not_interested`, `unknown`
- **`Speaker`**: `customer`, `agent`, `system`
- **`CallDirection`**: `outbound`
- **`CallProviderType`**: `browser`, `twilio`

---

## 10. Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://.../calling_agent_db` | Async SQLAlchemy PostgreSQL connection string |
| `APP_ENV` | `development` | Environment mode (`development`, `production`, `test`) |
| `SECRET_KEY` | `change-me-...` | Cryptographic secret key used for JWT signing |
| `ADMIN_EMAIL` | `admin@sephawk.com` | Seeded admin email address |
| `ADMIN_PASSWORD` | `Admin@123` | Initial seeded admin password |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `1440` | JWT token lifetime (24 hours) |
| `LOGIN_RATE_LIMIT` | `5` | Maximum login attempts within the rate-limit window |
| `LOGIN_RATE_WINDOW_SECONDS`| `60` | Login brute-force rate limit duration in seconds |
| `GEMINI_API_KEY` | `""` | Google AI Studio API key for Gemini 2.5 Flash |
| `LLM_PROVIDER` | `gemini` | LLM client provider (`gemini`) |
| `LLM_MODEL` | `gemini-2.5-flash` | Gemini model identifier |
| `LLM_MAX_RETRIES` | `2` | Retry attempts on transient LLM errors |
| `STT_PROVIDER` | `browser` | Speech-to-Text provider (`browser`) |
| `TTS_PROVIDER` | `browser` | Text-to-Speech provider (`browser`) |
| `CALL_PROVIDER` | `browser` | Telephony / voice bridge (`browser`, `twilio`) |
| `SILENCE_PROMPT_SECONDS` | `7.0` | Inactivity threshold before issuing a nudge |
| `SILENCE_MAX_PROMPTS` | `2` | Maximum nudges before terminating with `silence_timeout` |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | Allowed CORS origin for Next.js frontend |
| `SIMULATE_FAILURE` | `""` | Dev/demo failure simulation flag (`stt`, `llm`, `provider`) |
| `TWILIO_ACCOUNT_SID` | `""` | Optional Twilio account SID |
| `TWILIO_AUTH_TOKEN` | `""` | Optional Twilio authentication token |
| `TWILIO_PHONE_NUMBER` | `""` | Optional Twilio assigned phone number |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend backend API URL (in Next.js `.env.local`) |

---

## 11. Error Handling & Resilience

The application features multi-layer error handling across real-time voice and database transactions:

| Scenario | Trigger / Cause | Handled Call Status | Event Logged | Graceful Recovery Action |
| :--- | :--- | :--- | :--- | :--- |
| **STT Engine Error** | Browser speech recognition error (`network`, `audio-capture`) | Remains `in_progress` | `stt_failure` | Captures `recognition.onerror`, sends diagnostic payload to `/ws/call`, and auto-restarts speech recognition. |
| **LLM Outage / Timeout** | Gemini API rate limit, quota exhaustion, or network disconnect | Remains `in_progress` | `llm_failure` | Catches exceptions and transparently falls back to deterministic rule-based template phrasing. |
| **Provider Crash / Unhandled WS** | Exception inside WebSocket loop | Marks `failed` | `provider_error` | Closes socket with code 1011, records stack trace in `call_events`, and releases connection pool. |
| **Silence / No Response** | Customer stays silent for >7s | Transitions to `completed` after 2 prompts | `silence_timeout` | Nudges caller ("Are you still there?"), increments counter, and terminates cleanly if silence persists. |
| **Customer Interruption (Barge-in)** | Customer speaks while agent TTS audio is actively rendering | Remains `in_progress` | `interrupted` | Frontend cancels browser `speechSynthesis`, emits barge-in event, and processes new customer utterance. |
| **Abrupt Disconnect** | Network drop, tab closed, or navigation away mid-call | Marks `disconnected` | `disconnected` | Receives `WebSocketDisconnect`, runs shielded cleanup, persists partial turns, and generates summary of conversation had so far. |
| **Invalid Phone Number** | Number fails E.164 standard validation (e.g. not matching `^\+[1-9]\d{1,14}$`) | Marks `invalid_number` / rejects 422 | `invalid_number` | API rejects contact creation with 422 Unprocessable Entity; when attempted on call initiation, marks status `invalid_number`. |

---

## 12. Security Practices

- **Zero Hardcoded Secrets**: Secrets and API keys are strictly loaded via environment variables (`pydantic-settings`). `.gitignore` protects `.env` and `*.env.local`. `.env.example` contains only placeholder values.
- **WebSocket Query Param Authentication**: The `/ws/call/{call_id}?token={token}` endpoint validates JWT bearer tokens before accepting the connection. Unauthenticated or expired connections are rejected with close code `1008` (Policy Violation).
- **Non-Blocking Cryptography**: Password verification (`bcrypt.checkpw`) is offloaded to worker threads via `asyncio.to_thread` to prevent blocking the async FastAPI event loop.
- **Concurrency & Race Condition Guards**: `CallSession` turn processing and lifecycle transitions (`finish()`) are guarded with `asyncio.Lock` to prevent interleaved silence timeouts, customer utterances, or duplicate summaries.
- **Shielded Connection Cleanup**: Database session cleanup and summary persistence in the WebSocket `finally` block are wrapped in `anyio.CancelScope(shield=True)` so client disconnect cancellations cannot abort database commits.
- **SQL Injection Prevention**: Completely parameterized SQL queries via SQLAlchemy 2.0 ORM expressions.
- **Cross-Origin & CORS Protection**: Strict CORS origins whitelist restricting frontend domain access.

---

## 13. Project Structure

```
AI-Powered-Two-Way-Calling-Agent/
├── .env.example              # Environment variables template
├── .gitignore                # Protects secrets, node_modules, .venv
├── docker-compose.yml        # PostgreSQL container configuration
├── Agent.md                  # Technical design specification
├── README.md                 # Project documentation & runbook
├── backend/
│   ├── alembic/              # Database schema migrations
│   │   ├── versions/         # Alembic migration revisions
│   │   └── env.py
│   ├── alembic.ini
│   ├── app/
│   │   ├── agent/            # Conversational agent & FSM
│   │   │   ├── dialogue.py   # State machine dialogue engine
│   │   │   ├── extractor.py  # Regex & heuristic slot extractor
│   │   │   ├── llm.py        # Gemini 2.5 Flash client & retries
│   │   │   ├── prompts.py    # System instructions & persona
│   │   │   ├── slots.py      # Slot definitions & normalizers
│   │   │   └── summary.py    # Post-call summary & sentiment
│   │   ├── api/              # HTTP API endpoints
│   │   │   ├── deps.py       # Auth dependencies & rate limiters
│   │   │   └── v1/           # Modular route controllers
│   │   │       ├── auth.py
│   │   │       ├── calls.py
│   │   │       ├── contacts.py
│   │   │       └── dashboard.py
│   │   ├── core/             # Application configuration
│   │   │   ├── config.py     # Pydantic BaseSettings
│   │   │   ├── errors.py     # Global exception handlers
│   │   │   ├── logging.py    # Structured logging
│   │   │   └── security.py   # JWT & bcrypt password hashing
│   │   ├── db/               # Persistence layer
│   │   │   ├── base.py       # DeclarativeBase
│   │   │   ├── session.py    # Async engine & sessionmaker
│   │   │   └── models/       # SQLAlchemy 2.0 ORM models
│   │   │       ├── admin.py
│   │   │       ├── call.py
│   │   │       ├── call_event.py
│   │   │       ├── call_extracted_data.py
│   │   │       ├── call_summary.py
│   │   │       ├── call_turn.py
│   │   │       ├── contact.py
│   │   │       └── enums.py
│   │   ├── providers/        # Telephony abstraction layer
│   │   │   ├── base.py       # CallProvider interface
│   │   │   ├── browser.py    # Browser/WebSocket voice provider
│   │   │   └── twilio.py     # Twilio Media Streams provider
│   │   ├── realtime/         # Real-time WebSocket audio layer
│   │   │   ├── call_session.py # Turn concurrency & lifecycle
│   │   │   └── ws.py         # Duplex WebSocket router
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   │   ├── auth.py
│   │   │   ├── call.py
│   │   │   ├── contact.py
│   │   │   └── dashboard.py
│   │   ├── services/         # Business logic layer
│   │   │   ├── call_service.py
│   │   │   ├── contact_service.py
│   │   │   └── summary_service.py
│   │   └── main.py           # FastAPI application factory
│   ├── pyproject.toml        # Ruff, Black, Pytest configuration
│   ├── requirements.txt      # Python dependencies
│   ├── scripts/
│   │   └── seed_db.py        # Database seeding utility
│   └── tests/                # Automated pytest suite (102 tests)
│       ├── conftest.py
│       ├── test_agent_dialogue.py
│       ├── test_agent_llm.py
│       ├── test_auth.py
│       ├── test_calls.py
│       ├── test_config.py
│       ├── test_contacts.py
│       ├── test_dashboard.py
│       ├── test_e2e_flow.py
│       ├── test_errors.py
│       ├── test_health.py
│       ├── test_security.py
│       ├── test_summary.py
│       └── test_ws.py
├── database/
│   ├── schema.sql            # Direct SQL schema DDL
│   ├── seed.sql              # Raw SQL seed script
│   └── ERD.md                # Entity relationship documentation
└── frontend/
    ├── app/                  # Next.js 15 App Router pages
    │   ├── calls/
    │   │   ├── [id]/page.jsx # Call dossier, transcript & slots
    │   │   └── page.jsx      # Paginated call history with 7 filters
    │   ├── contacts/
    │   │   └── page.jsx      # Contact directory & "Start Call"
    │   ├── dashboard/
    │   │   └── page.jsx      # Live KPI metrics & duration stats
    │   ├── live-call/
    │   │   └── [id]/page.jsx # Voice call with STT, TTS & barge-in
    │   ├── login/
    │   │   └── page.jsx      # Authentication form
    │   ├── layout.jsx        # Shared layout with Auth Guard & Navbar
    │   └── page.jsx          # Redirect to /dashboard
    ├── components/
    │   └── Navbar.jsx        # Navigation bar & logout
    ├── lib/
    │   └── api.js            # Fetch wrapper with Bearer token & 401 redirect
    ├── next.config.mjs
    └── package.json
```

---

## 14. Testing

The backend includes a comprehensive automated test suite with **102 tests** covering every layer:
- **Unit & Property Tests**: Slot extraction regex, FSM phase transitions, rule-based fallback responses.
- **LLM Client & Resilience**: Gemini API retries, JSON parsing recovery, fallback on rate-limits.
- **Security & Auth**: Password hashing rounds, JWT expiration, login rate-limiting brute-force defense.
- **REST Endpoints**: CRUD operations for contacts, filtered call queries, pagination, analytics KPI math.
- **WebSocket & Realtime Lifecycle**: Handshake authentication with query param tokens, continuous speech turns, silence timeout intervals, barge-in interrupts, unhandled exception error logging, and graceful disconnect persistence.
- **End-to-End Integration Flow**: Full multi-turn conversation and post-call analysis verification.

### Run the Test Suite
```bash
cd backend
python -m pytest -v
```

Output:
```
tests/test_agent_dialogue.py ............                                [ 11%]
tests/test_agent_llm.py ...............                                  [ 26%]
tests/test_auth.py ........                                              [ 34%]
tests/test_calls.py ..................                                   [ 52%]
tests/test_config.py ...                                                 [ 55%]
tests/test_contacts.py ........                                          [ 63%]
tests/test_dashboard.py ...                                              [ 66%]
tests/test_e2e_flow.py .                                                 [ 67%]
tests/test_errors.py ....                                                [ 71%]
tests/test_health.py ...                                                 [ 74%]
tests/test_security.py .....                                             [ 79%]
tests/test_summary.py .........                                          [ 88%]
tests/test_ws.py .............                                           [100%]

============================ 102 passed in 27.22s =============================
```

### Run Code Formatters & Linters
```bash
cd backend
python -m ruff check .
python -m black --check .
```

### Run Frontend Production Build
```bash
cd frontend
npm run build
```

---

## 15. Free-Tier Limitations

- **Google Gemini Flash API Quota**: Subject to Google AI Studio free-tier rate limits (15 requests/minute). High-frequency calls will automatically drop to rule-based fallback mode upon 429 quota exhaustion.
- **Web Speech API Browser Compatibility**: Continuous STT via `webkitSpeechRecognition` is supported natively in Chromium-based browsers (Google Chrome, Microsoft Edge, Brave). Firefox and Safari require the Web Speech polyfill or Edge-TTS backend.
- **Twilio Trial Restrictions**: Twilio trial accounts require pre-verified recipient phone numbers and carrier compliance. In this demo, `CALL_PROVIDER=browser` is selected by default to allow unlimited, cost-free interactive voice testing directly through the browser.

---

## 16. Future Improvements

- **WebRTC Audio Streaming**: Implement bi-directional Opus-encoded WebRTC audio streaming to replace browser-level Web Speech API with server-side Whisper STT.
- **Production Telephony (Twilio / Asterisk)**: Connect Twilio Voice Media Streams directly to a server-side WebSocket pipeline for real inbound and outbound phone PSTN calling.
- **Voice Cloned TTS**: Integrate ElevenLabs or Cartesia low-latency streaming TTS API for human-like conversational inflection and breath pauses.
- **Automated CRM Sync**: Webhook dispatch to Salesforce, HubSpot, or Zoho CRM when a call outcome is marked as `hot` or `interested`.
- **Multi-lingual / Indian Regional Dialects**: Extend language model prompting and STT configuration to Hindi, Kannada, Tamil, and Telugu for Pan-Indian industrial markets.
