"""CLI simulation — run the agent turn-by-turn against a scripted conversation.

Usage (from ``backend/``):

    python -m app.agent.cli                # canonical demo conversation
    python -m app.agent.cli --interactive  # read your own turns from stdin
    python -m app.agent.cli --turn "hi" --turn "500 LPH"   # custom script

Prints every agent reply and the slot state after every turn (audit D16),
then the post-call summary JSON (audit D18).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

from app.agent.dialogue import AgentTurn, DialogueAgent
from app.agent.llm import LLMClient, get_llm
from app.agent.summary import generate_summary
from app.db.models.enums import CallOutcome, LeadStatus

# The canonical audit conversation (AGENT.md §8 / audit check D16)
DEMO_TURNS: list[str] = [
    "I need a commercial RO system for my hotel",
    "500 LPH",
    "Bangalore",
    "around 1 lakh",
    "within a month",
    "my name is Rahul Kumar",
]


async def run_conversation(
    turns: Sequence[str],
    *,
    llm: LLMClient | None = None,
    write=print,
) -> tuple[DialogueAgent, list[str]]:
    """Feed *turns* through a fresh agent, echoing replies + slot state.

    Returns ``(agent, transcript)`` where transcript lines are
    ``customer: ...`` / ``agent: ...`` pairs in order.
    """
    agent = DialogueAgent(llm=llm)
    transcript: list[str] = []
    for index, user_text in enumerate(turns, start=1):
        write(f"\n--- Turn {index} " + "-" * 46)
        write(f"USER  : {user_text}")
        result: AgentTurn = await agent.handle(user_text)
        transcript.append(f"customer: {user_text}")
        transcript.append(f"agent: {result.reply}")
        write(f"AGENT : {result.reply}")
        write(f"STATE : {result.state}")
        write(f"SLOTS : {json.dumps(result.slots, ensure_ascii=False, indent=2)}")
    return agent, transcript


def _read_interactive_turns() -> list[str]:
    print("Interactive mode — empty line or Ctrl-D ends input.")
    turns: list[str] = []
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        turns.append(line)
    return turns


async def amain(args: argparse.Namespace) -> int:
    llm = get_llm()
    turns = _read_interactive_turns() if args.interactive else (args.turn or DEMO_TURNS)
    if not turns:
        print("No turns supplied.")
        return 1

    agent, transcript = await run_conversation(turns, llm=llm)

    print("\n=== Post-call summary ===")
    summary, source = await generate_summary(
        llm,
        agent.slots.as_dict(),
        transcript,
        not_interested=agent.not_interested,
    )
    print(f"source: {source}")
    print(summary.model_dump_json(indent=2))

    # D18: the payload must always carry exactly the contract fields
    data = summary.model_dump()
    expected = {
        "summary",
        "key_requirements",
        "customer_intent",
        "important_points",
        "followup_actions",
        "outcome",
        "lead_status",
        "followup_required",
    }
    assert set(data) == expected, f"summary fields mismatch: {set(data)}"
    assert data["outcome"] in {o.value for o in CallOutcome}
    assert data["lead_status"] in {ls.value for ls in LeadStatus}
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI calling agent — CLI simulation")
    parser.add_argument("--interactive", action="store_true", help="read turns from stdin")
    parser.add_argument("--turn", action="append", help="repeatable: one utterance per flag")
    args = parser.parse_args(argv)
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
