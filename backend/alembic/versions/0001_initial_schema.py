"""Initial schema — all 7 tables, 6 enum types, all indexes.

Revision ID: 0001
Revises:
Create Date: 2026-09-29

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create PostgreSQL enum types ───────────────────────────────────────
    postgresql.ENUM(
        "outbound", name="call_direction", create_type=True
    ).create(conn, checkfirst=True)

    postgresql.ENUM(
        "browser", "twilio", name="call_provider", create_type=True
    ).create(conn, checkfirst=True)

    postgresql.ENUM(
        "queued", "ringing", "in_progress", "completed",
        "no_answer", "failed", "disconnected", "invalid_number",
        name="call_status", create_type=True,
    ).create(conn, checkfirst=True)

    postgresql.ENUM(
        "interested", "not_interested", "callback_requested",
        "no_response", "failed", "incomplete",
        name="call_outcome", create_type=True,
    ).create(conn, checkfirst=True)

    postgresql.ENUM(
        "hot", "warm", "cold", "interested", "not_interested", "unknown",
        name="lead_status", create_type=True,
    ).create(conn, checkfirst=True)

    postgresql.ENUM(
        "customer", "agent", "system", name="speaker_type", create_type=True
    ).create(conn, checkfirst=True)

    # ── 2. admins ─────────────────────────────────────────────────────────────
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admins"),
    )
    op.create_index("ix_admins_email", "admins", ["email"], unique=True)

    # ── 3. contacts ───────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("product", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_contacts"),
    )

    # ── 4. calls ──────────────────────────────────────────────────────────────
    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column(
            "direction",
            postgresql.ENUM("outbound", name="call_direction", create_type=False),
            nullable=False,
            server_default="outbound",
        ),
        sa.Column(
            "provider",
            postgresql.ENUM("browser", "twilio", name="call_provider", create_type=False),
            nullable=False,
            server_default="browser",
        ),
        sa.Column("provider_call_sid", sa.String(255), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued", "ringing", "in_progress", "completed",
                "no_answer", "failed", "disconnected", "invalid_number",
                name="call_status", create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "outcome",
            postgresql.ENUM(
                "interested", "not_interested", "callback_requested",
                "no_response", "failed", "incomplete",
                name="call_outcome", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "lead_status",
            postgresql.ENUM(
                "hot", "warm", "cold", "interested", "not_interested", "unknown",
                name="lead_status", create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "followup_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["contacts.id"],
            name="fk_calls_contact_id_contacts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calls"),
    )
    # Individual indexes per AGENT.md §5
    op.create_index("ix_calls_status", "calls", ["status"])
    op.create_index("ix_calls_outcome", "calls", ["outcome"])
    op.create_index("ix_calls_lead_status", "calls", ["lead_status"])
    op.create_index("ix_calls_followup_required", "calls", ["followup_required"])
    op.create_index("ix_calls_start_time", "calls", ["start_time"])

    # ── 5. call_turns ─────────────────────────────────────────────────────────
    op.create_table(
        "call_turns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column(
            "speaker",
            postgresql.ENUM(
                "customer", "agent", "system",
                name="speaker_type", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["call_id"], ["calls.id"], name="fk_call_turns_call_id_calls"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_call_turns"),
    )
    # Composite index for fast ordered transcript fetch
    op.create_index(
        "ix_call_turns_call_id_turn_index", "call_turns", ["call_id", "turn_index"]
    )

    # ── 6. call_extracted_data ────────────────────────────────────────────────
    op.create_table(
        "call_extracted_data",
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("requirement", sa.Text(), nullable=True),
        sa.Column("ro_capacity_lph", sa.String(100), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("application", sa.String(255), nullable=True),
        sa.Column("budget", sa.String(255), nullable=True),
        sa.Column("timeline", sa.String(255), nullable=True),
        sa.Column("additional_requirements", sa.Text(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["call_id"], ["calls.id"],
            name="fk_call_extracted_data_call_id_calls",
        ),
        sa.PrimaryKeyConstraint("call_id", name="pk_call_extracted_data"),
    )

    # ── 7. call_summaries ─────────────────────────────────────────────────────
    op.create_table(
        "call_summaries",
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("key_requirements", postgresql.JSONB(), nullable=True),
        sa.Column("customer_intent", sa.Text(), nullable=True),
        sa.Column("important_points", postgresql.JSONB(), nullable=True),
        sa.Column("followup_actions", postgresql.JSONB(), nullable=True),
        sa.Column(
            "outcome",
            postgresql.ENUM(
                "interested", "not_interested", "callback_requested",
                "no_response", "failed", "incomplete",
                name="call_outcome", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "lead_status",
            postgresql.ENUM(
                "hot", "warm", "cold", "interested", "not_interested", "unknown",
                name="lead_status", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "followup_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["call_id"], ["calls.id"],
            name="fk_call_summaries_call_id_calls",
        ),
        sa.PrimaryKeyConstraint("call_id", name="pk_call_summaries"),
    )

    # ── 8. call_events ────────────────────────────────────────────────────────
    op.create_table(
        "call_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["call_id"], ["calls.id"], name="fk_call_events_call_id_calls"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_call_events"),
    )
    op.create_index("ix_call_events_call_id", "call_events", ["call_id"])


def downgrade() -> None:
    # Drop tables in reverse FK order
    op.drop_table("call_events")
    op.drop_table("call_summaries")
    op.drop_table("call_extracted_data")
    op.drop_table("call_turns")
    op.drop_table("calls")
    op.drop_table("contacts")
    op.drop_table("admins")

    # Drop enum types
    conn = op.get_bind()
    postgresql.ENUM(name="speaker_type").drop(conn, checkfirst=True)
    postgresql.ENUM(name="lead_status").drop(conn, checkfirst=True)
    postgresql.ENUM(name="call_outcome").drop(conn, checkfirst=True)
    postgresql.ENUM(name="call_status").drop(conn, checkfirst=True)
    postgresql.ENUM(name="call_provider").drop(conn, checkfirst=True)
    postgresql.ENUM(name="call_direction").drop(conn, checkfirst=True)
