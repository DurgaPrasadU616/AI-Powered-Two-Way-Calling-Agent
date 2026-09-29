# Entity-Relationship Diagram — AI Calling Agent

## Tables

| Table | PK | Key Columns |
|---|---|---|
| `admins` | `id` INT | email (unique), password_hash |
| `contacts` | `id` INT | name, phone_e164, company, purpose, product |
| `calls` | `id` UUID | contact_id FK→contacts, phone_number, direction, provider, status, outcome, lead_status, followup_required, start/end_time |
| `call_turns` | `id` INT | call_id FK→calls, turn_index, speaker, message, confidence |
| `call_extracted_data` | `call_id` UUID (FK→calls) | 9 slot columns + raw_json JSONB |
| `call_summaries` | `call_id` UUID (FK→calls) | summary, key_requirements, customer_intent, important_points, followup_actions, outcome, lead_status |
| `call_events` | `id` INT | call_id FK→calls, event_type, detail JSONB |

## Relationships

```
contacts  ──<  calls  ──<  call_turns
                │
                ├──1  call_extracted_data
                ├──1  call_summaries
                └──<  call_events
```

## Enum Types (PostgreSQL)

| Name | Values |
|---|---|
| `call_direction` | outbound |
| `call_provider` | browser, twilio |
| `call_status` | queued, ringing, in_progress, completed, no_answer, failed, disconnected, invalid_number |
| `call_outcome` | interested, not_interested, callback_requested, no_response, failed, incomplete |
| `lead_status` | hot, warm, cold, interested, not_interested, unknown |
| `speaker_type` | customer, agent, system |

## Indexes

| Table | Index | Type |
|---|---|---|
| `admins` | `email` | unique |
| `calls` | `status`, `outcome`, `lead_status`, `followup_required`, `start_time` | btree |
| `call_turns` | `(call_id, turn_index)` | composite btree |
| `call_events` | `call_id` | btree |
