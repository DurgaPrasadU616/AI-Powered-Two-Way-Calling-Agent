"""Add ON DELETE CASCADE to call foreign keys.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29 22:30:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    # Drop existing FK constraints
    op.drop_constraint("fk_call_turns_call_id_calls", "call_turns", type_="foreignkey")
    op.drop_constraint("fk_call_extracted_data_call_id_calls", "call_extracted_data", type_="foreignkey")
    op.drop_constraint("fk_call_summaries_call_id_calls", "call_summaries", type_="foreignkey")
    op.drop_constraint("fk_call_events_call_id_calls", "call_events", type_="foreignkey")

    # Re-create with ON DELETE CASCADE
    op.create_foreign_key(
        "fk_call_turns_call_id_calls",
        "call_turns",
        "calls",
        ["call_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_call_extracted_data_call_id_calls",
        "call_extracted_data",
        "calls",
        ["call_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_call_summaries_call_id_calls",
        "call_summaries",
        "calls",
        ["call_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_call_events_call_id_calls",
        "call_events",
        "calls",
        ["call_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Drop CASCADE constraints
    op.drop_constraint("fk_call_turns_call_id_calls", "call_turns", type_="foreignkey")
    op.drop_constraint("fk_call_extracted_data_call_id_calls", "call_extracted_data", type_="foreignkey")
    op.drop_constraint("fk_call_summaries_call_id_calls", "call_summaries", type_="foreignkey")
    op.drop_constraint("fk_call_events_call_id_calls", "call_events", type_="foreignkey")

    # Restore standard FK constraints without CASCADE
    op.create_foreign_key(
        "fk_call_turns_call_id_calls",
        "call_turns",
        "calls",
        ["call_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_call_extracted_data_call_id_calls",
        "call_extracted_data",
        "calls",
        ["call_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_call_summaries_call_id_calls",
        "call_summaries",
        "calls",
        ["call_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_call_events_call_id_calls",
        "call_events",
        "calls",
        ["call_id"],
        ["id"],
    )
