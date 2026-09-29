-- =============================================================================
-- AI Calling Agent — PostgreSQL Schema (Reference)
-- =============================================================================
-- This file mirrors the Alembic migration for documentation and manual use.
-- For application use: run `alembic upgrade head` from backend/ instead.
-- =============================================================================

-- Enable gen_random_uuid() (built-in since PG 13, no extension needed in PG 15)

-- ── Enum types ────────────────────────────────────────────────────────────────
CREATE TYPE call_direction AS ENUM ('outbound');

CREATE TYPE call_provider AS ENUM ('browser', 'twilio');

CREATE TYPE call_status AS ENUM (
    'queued', 'ringing', 'in_progress', 'completed',
    'no_answer', 'failed', 'disconnected', 'invalid_number'
);

CREATE TYPE call_outcome AS ENUM (
    'interested', 'not_interested', 'callback_requested',
    'no_response', 'failed', 'incomplete'
);

CREATE TYPE lead_status AS ENUM (
    'hot', 'warm', 'cold', 'interested', 'not_interested', 'unknown'
);

CREATE TYPE speaker_type AS ENUM ('customer', 'agent', 'system');

-- ── admins ────────────────────────────────────────────────────────────────────
CREATE TABLE admins (
    id           SERIAL PRIMARY KEY,
    email        VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_admins_email UNIQUE (email)
);
CREATE UNIQUE INDEX ix_admins_email ON admins (email);

-- ── contacts ──────────────────────────────────────────────────────────────────
CREATE TABLE contacts (
    id          SERIAL      PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    phone_e164  VARCHAR(20)  NOT NULL,          -- E.164 format e.g. +919876543210
    company     VARCHAR(255),
    purpose     TEXT,
    product     VARCHAR(255),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── calls ─────────────────────────────────────────────────────────────────────
CREATE TABLE calls (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        INTEGER      REFERENCES contacts(id) ON DELETE SET NULL,
    phone_number      VARCHAR(20)  NOT NULL,
    direction         call_direction  NOT NULL DEFAULT 'outbound',
    provider          call_provider   NOT NULL DEFAULT 'browser',
    provider_call_sid VARCHAR(255),
    status            call_status     NOT NULL DEFAULT 'queued',
    outcome           call_outcome,
    start_time        TIMESTAMPTZ,
    end_time          TIMESTAMPTZ,
    duration_seconds  INTEGER,
    lead_status       lead_status     NOT NULL DEFAULT 'unknown',
    followup_required BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
-- Indexes per AGENT.md §5
CREATE INDEX ix_calls_status           ON calls (status);
CREATE INDEX ix_calls_outcome          ON calls (outcome);
CREATE INDEX ix_calls_lead_status      ON calls (lead_status);
CREATE INDEX ix_calls_followup_required ON calls (followup_required);
CREATE INDEX ix_calls_start_time       ON calls (start_time);

-- ── call_turns ────────────────────────────────────────────────────────────────
CREATE TABLE call_turns (
    id          SERIAL       PRIMARY KEY,
    call_id     UUID         NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    turn_index  INTEGER      NOT NULL,
    speaker     speaker_type NOT NULL,
    message     TEXT         NOT NULL,
    confidence  FLOAT,                          -- STT confidence 0.0–1.0
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
-- Composite index for ordered transcript fetch
CREATE INDEX ix_call_turns_call_id_turn_index ON call_turns (call_id, turn_index);

-- ── call_extracted_data ───────────────────────────────────────────────────────
-- One row per call; updated live as agent extracts slots.
CREATE TABLE call_extracted_data (
    call_id                 UUID         PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    customer_name           VARCHAR(255),
    company_name            VARCHAR(255),
    requirement             TEXT,
    ro_capacity_lph         VARCHAR(100),
    location                VARCHAR(255),
    application             VARCHAR(255),
    budget                  VARCHAR(255),
    timeline                VARCHAR(255),
    additional_requirements TEXT,
    raw_json                JSONB,              -- full LLM extractor output
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── call_summaries ────────────────────────────────────────────────────────────
-- One row per call; written post-call by summary_service.
CREATE TABLE call_summaries (
    call_id          UUID         PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    summary          TEXT,
    key_requirements JSONB,
    customer_intent  TEXT,
    important_points JSONB,
    followup_actions JSONB,
    outcome          call_outcome,
    lead_status      lead_status,
    followup_required BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── call_events ───────────────────────────────────────────────────────────────
-- Append-only event log: lifecycle + errors.
-- event_type values: no_answer | silence_timeout | stt_failure | llm_failure |
--                    interrupted | provider_error | disconnected |
--                    call_started | call_ended | turn_saved
CREATE TABLE call_events (
    id          SERIAL       PRIMARY KEY,
    call_id     UUID         NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    event_type  VARCHAR(100) NOT NULL,
    detail      JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_call_events_call_id ON call_events (call_id);
