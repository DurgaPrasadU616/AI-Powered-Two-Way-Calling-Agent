# AGENT.md — AI-Powered Two-Way Calling Agent

> **Reconstructed 2026-09-29 from surviving references** (`database/schema.sql` §5,
> `docker-compose.yml` §3, `database/ERD.md`, backend source, and the verification
> audit checklist A–F). This file is the single source of truth for the build.

---

## 1. Overview

An outbound AI sales agent that calls leads by voice, qualifies them for
**commercial/industrial RO (reverse-osmosis) systems** (SERP Hawk product line),
collects structured requirements turn-by-turn, and produces a post-call summary
with outcome, lead status and follow-up flag.

Two-way conversation: the customer speaks, the agent replies — one question at a
time, voice-friendly, context-aware.

## 2. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn, SQLAlchemy 2.0 (async), Alembic, asyncpg |
| DB | PostgreSQL 15+ (local PG 18 used on this machine) |
| Auth | bcrypt (12 rounds) + PyJWT (HS256), env-configured admin, no self-registration |
| LLM | Google Gemini free tier (`google-genai`), provider-abstracted, retry + deterministic fallback |
| STT/TTS | Browser Web Speech API (default) — provider interfaces allow whisper/edge later |
| Calling | Browser WebSocket (default) — Twilio optional (Phase 7) |
| Frontend | Next.js (App Router) in `/frontend`, Tailwind-free minimal UI |
| Validation | Pydantic v2 everywhere; `phonenumbers` for E.164 |
| Tooling | ruff (lint), black (format), pytest + pytest-asyncio (auto mode) |

## 3. Environment & infrastructure

- Postgres via **local installation** (PG 18, psql at `C:\Program Files\PostgreSQL\18\bin`);
  `docker-compose.yml` provided for portability but Docker is optional
  (skip when a local PG already listens on 5432).
- Databases: `calling_agent_db` (dev), `calling_agent_test` (tests).
- Secrets live only in `backend/.env` — **never committed**; `.env.example` carries
  placeholders only. `.gitignore` covers `.env`, `*.env.local`.
- Config is read once via `pydantic-settings` (`app/core/config.py`), file resolved
  relative to the package so any CWD works.

## 4. Folder structure

```
AI-Powered-Two-Way-Calling-Agent/
├── Agent.md                  # this spec
├── README.md
├── .gitignore
├── .env.example              # placeholders only
├── docker-compose.yml        # optional Postgres
├── database/
│   ├── schema.sql            # reference DDL (mirrors migration)
│   ├── seed.sql              # reference seed (mirrors scripts/seed_db.py)
│   └── ERD.md
├── backend/
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── pyproject.toml        # ruff/black/pytest config
│   ├── .env                  # real secrets (git-ignored)
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial_schema.py
│   ├── scripts/
│   │   └── seed_db.py        # admin + contacts seed (idempotent)
│   ├── app/
│   │   ├── main.py           # app factory, CORS, handlers, /health, router wiring
│   │   ├── core/             # config, security, errors, logging
│   │   ├── db/               # base, session, models/{admin,contact,call,call_turn,
│   │   │                     #   call_extracted_data,call_summary,call_event,enums}
│   │   ├── schemas/          # pydantic: auth, contact, call, dashboard, summary
│   │   ├── api/v1/           # auth, contacts, calls, dashboard routers (+ deps)
│   │   ├── services/         # call_service, summary_service
│   │   ├── agent/            # slots, dialogue, llm, summary, cli (Phase 3)
│   │   ├── providers/        # CallProvider/STT/TTS interfaces + browser impls
│   │   └── realtime/         # call_session, ws router (Phase 4)
│   └── tests/                # pytest suite (per-phase test modules)
└── frontend/                 # Next.js app (Phase 4)
    └── app/live-call/[id]/   # browser voice page
```

## 5. Database

7 tables + `alembic_version`; 6 enum types. Authoritative DDL: `database/schema.sql`
and `backend/alembic/versions/0001_initial_schema.py`.

Tables: `admins`, `contacts`, `calls`, `call_turns`, `call_extracted_data`,
`call_summaries`, `call_events` (ERD in `database/ERD.md`).

Enums: `call_direction`, `call_provider`, `call_status`, `call_outcome`,
`lead_status`, `speaker_type`.

Required indexes:
- `calls`: `status`, `outcome`, `lead_status`, `followup_required`, `start_time`
- `call_turns`: composite `(call_id, turn_index)`
- `call_events`: `call_id`
- `admins`: unique `email`

Seed (`scripts/seed_db.py`, idempotent): 1 admin (bcrypt `$2b$` hash of
`ADMIN_PASSWORD`) + 2 contacts (Rahul Kumar / Priya Sharma, E.164 `+91…`).

## 6. Phases

| Phase | Scope | Commit message |
|---|---|---|
| 1 | Skeleton: app factory, config, security, errors, logging, models, migration 0001, seed script, smoke tests | `feat: phase 1 backend skeleton` |
| 2 | REST API: auth/login (+rate limit), contacts CRUD (E.164 422), calls create/end/detail + **all list filters + pagination**, dashboard stats, error-leak tests | `feat: phase 2 rest api` |
| 3 | Agent core: slot dialogue state machine, Gemini client w/ retry+fallback, post-call summary (Pydantic + rule-based fallback), CLI simulation, behaviour tests | `feat: phase 3 agent core` |
| 4 | Realtime & browser voice: providers, `call_session`, `/ws/call/{id}`, silence + barge-in, live persistence, call end/disconnect handling, Next.js `/live-call/[id]`, WS test | `feat: phase 4 realtime voice` |
| 5+ | Batch calling, dashboards UI, Twilio (optional) | — |

Verification audit (checks A–F, §7/§8) runs **before** Phase 4 and lands as
`fix: verification audit`.

## 7. API contract (Phase 2)

All under `/docs` (OpenAPI). Auth: `Authorization: Bearer <JWT>`.

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | 200, no auth |
| POST | `/auth/login` | `{email,password}` → `{access_token,token_type}`; wrong password ⇒ 401; rate-limited (in-memory sliding window, 429) |
| GET/POST | `/contacts` | list (search/pagination) / create |
| GET/PATCH/DELETE | `/contacts/{id}` | delete ⇒ 204; unknown id ⇒ 404 |
| POST | `/calls` | creates call, `status=queued` |
| POST | `/calls/{id}/end` | sets `end_time`, `duration_seconds`, `status=completed` |
| GET | `/calls` | filters **each** of: `date_from`, `date_to`, `customer` (contact id/name), `status`, `lead_status`, `followup_required`, `outcome`; plus `page`, `page_size` |
| GET | `/calls/{id}` | call info + `turns` + `extracted_data` + `summary` + `events` |
| GET | `/dashboard/stats` | `total_calls`, `completed_calls`, `failed_calls`, `interested_leads`, `followups_required`, `avg_duration_seconds` |

Validation: any phone that is not valid E.164 (e.g. `12345`) ⇒ **422**;
`+919876543210` ⇒ accepted. Errors return structured JSON
(`{"detail":…,"status_code":…}`) with **no stack traces**, ever — including 500s.

## 8. Agent behaviour spec (Phase 3/4)

Slots (in ask order): `requirement`, `capacity`, `location`, `budget`, `timeline`,
`customer_name` (+ optional `company`, `application`, `additional_requirements`).

Required behaviours (audit checks D17 a–h):
- (a) asks **one** question per reply;
- (b) never re-asks a slot already filled;
- (c) references earlier context in phrasing (e.g. "for your hotel");
- (d) a filled slot is **never** overwritten with `null`/empty;
- (e) a customer question is answered, then the agent returns to the next missing slot;
- (f) "not interested" ⇒ immediate `WRAP_UP` state;
- (g) replies are short, single-sentence, voice-friendly — **no lists, no markdown**;
- (h) conversation ends (`WRAP_UP`) once all required slots are filled.

Post-call summary — Pydantic model `CallSummaryCreate`, **all** fields required:
`summary`, `key_requirements`, `customer_intent`, `important_points`,
`followup_actions`, `outcome`, `lead_status`, `followup_required`.
LLM JSON parse failure ⇒ retry (n) then rule-based fallback built from slots +
transcript. LLM transport failure ⇒ same.

## 9. Realtime contract (Phase 4)

- `WS /ws/call/{call_id}`; client→server: `customer_speech`, `interrupt`,
  `end_call`; server→client: `agent_reply`, `state_update`, `call_status`, `error`.
- Every turn persisted to `call_turns`; slots upserted to `call_extracted_data` live.
- Opening line is templated (uses contact name/company when known).
- Silence: prompt at ~7s, prompt again at ~7s, then end ⇒ `call_events.silence_timeout`.
- Barge-in: client `interrupt` ⇒ `call_events.interrupted` logged, client cancels TTS.
- Call end: `end_time` + `duration_seconds`, summary generated & stored, `outcome`,
  `lead_status`, `followup_required` set. Socket drop ⇒ `status=disconnected` and the
  partial transcript is still summarized.
- Frontend `/live-call/[id]`: Web Speech API mic, `speechSynthesis` replies, live
  transcript, End Call button, agent-speaking indicator. **Chrome recommended.**

## 10. Quality gates

- `ruff check .` and `black --check .` clean from `backend/` (line length 100;
  `alembic/versions` excluded from both).
- `pytest -v` from `backend/` — all green; async tests via pytest-asyncio auto mode.
- No hardcoded secrets/keys/URLs outside config: grep must find no `AIza…`,
  no literal `secret` assignments, no `localhost` outside config/docker-compose.
- No `TODO`/`FIXME`/dead code left in `app/`.

## 11. Git conventions

One commit per phase (messages in §6), `fix: verification audit` for audit fixes.
Never commit `backend/.env`, `__pycache__`, `.next`, `node_modules`.
