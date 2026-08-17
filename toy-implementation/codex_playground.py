#!/usr/bin/env python3
"""
Run
---
    backend/.venv/bin/python codex_playground.py
    backend/.venv/bin/python codex_playground.py "add a footer to the home page"
"""

import os
import sys
import time
from pathlib import Path
import asyncio

from openai_codex import AsyncCodex, CodexConfig, Sandbox
from openai_codex._run import (
    _final_assistant_response_from_items,
    _raise_for_failed_turn,
)
from openai_codex.generated.v2_all import (
    ItemCompletedNotification,
    ItemStartedNotification,
    ListMcpServerStatusResponse,
    ReasoningEffort,
    ThreadTokenUsageUpdatedNotification,
    TurnCompletedNotification,
)

HERE = Path(__file__).parent
WORKSPACE = HERE / "base2"  # the codebase we hand to the agent
CODEX_HOME = HERE / ".codex_playground_home"  # our own auth + session storage

DEFAULT_PROMPT = "Add a toast notification successfully showing that a task was added, should show on the bottom right"

MODEL = "gpt-5.6"
EFFORT: ReasoningEffort | None = (
    None  # e.g. ReasoningEffort.low to trade quality for speed
)
SANDBOX = Sandbox.workspace_write


def _hr(title: str = "") -> None:
    line = "=" * 70
    if title:
        print(f"\n{line}\n {title}\n{line}")
    else:
        print(line)


def _unwrap(item):
    return item.root if hasattr(item, "root") else item


def _count_reasoning_steps(items) -> int:
    """Lower bound on model round trips: not every call emits a reasoning item."""
    return sum(
        1 for item in items if getattr(_unwrap(item), "type", None) == "reasoning"
    )


def _categorize(node) -> tuple[str, str]:
    """Map a thread item to (grouping category, human-readable label)."""
    if node.type == "commandExecution":
        return "shell", node.command.strip().replace("\n", " ")[:60]
    if node.type == "mcpToolCall":
        label = f"mcp:{node.server}.{node.tool}"
        return label, label
    if node.type == "dynamicToolCall":
        label = f"tool:{node.tool}"
        return label, label
    if node.type == "reasoning":
        return "reasoning", "reasoning"
    if node.type == "agentMessage":
        phase = node.phase.value if node.phase else "unphased"
        label = f"writing:{phase}"
        return label, label
    return node.type, node.type


async def _run_turn_with_breakdown(thread, input_text, **turn_kwargs):
    """Run a turn via the streaming API and time every item, not just tool calls.

    `thread.run()` only keeps each item's final `duration_ms`, which is only
    populated for commandExecution/mcpToolCall/dynamicToolCall items. Reasoning
    and agentMessage items carry no duration at all in the collected result, so
    to separate "thinking" time from "writing" time we consume the raw
    `item/started` / `item/completed` notification stream ourselves and time
    every item from its own start/end timestamps.
    """
    handle = await thread.turn(input_text, **turn_kwargs)
    item_started_ms: dict[str, int] = {}
    items = []
    entries: list[tuple[str, str, int]] = []
    usage = None
    completed = None

    stream = handle.stream()
    try:
        async for event in stream:
            payload = event.payload
            if (
                isinstance(payload, ItemStartedNotification)
                and payload.turn_id == handle.id
            ):
                item_started_ms[_unwrap(payload.item).id] = payload.started_at_ms
            elif (
                isinstance(payload, ItemCompletedNotification)
                and payload.turn_id == handle.id
            ):
                node = _unwrap(payload.item)
                items.append(payload.item)
                duration_ms = getattr(node, "duration_ms", None)
                if duration_ms is None:
                    start_ms = item_started_ms.pop(node.id, None)
                    if start_ms is not None:
                        duration_ms = payload.completed_at_ms - start_ms
                if duration_ms is not None:
                    category, label = _categorize(node)
                    entries.append((category, label, duration_ms))
            elif (
                isinstance(payload, ThreadTokenUsageUpdatedNotification)
                and payload.turn_id == handle.id
            ):
                usage = payload.token_usage
            elif (
                isinstance(payload, TurnCompletedNotification)
                and payload.turn.id == handle.id
            ):
                completed = payload
    finally:
        await stream.aclose()

    if completed is None:
        raise RuntimeError("turn completed event not received")
    _raise_for_failed_turn(completed.turn)
    final_response = _final_assistant_response_from_items(items)
    return completed.turn, items, usage, final_response, entries


def _print_time_breakdown(
    entries, turn_duration_ms: int | None, indent: str = "  "
) -> None:
    if not entries:
        print(f"{indent}(no timed items)")
        return

    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for category, _, duration_ms in entries:
        totals[category] = totals.get(category, 0) + duration_ms
        counts[category] = counts.get(category, 0) + 1
    accounted_ms = sum(totals.values())

    for category, duration_ms in sorted(totals.items(), key=lambda kv: -kv[1]):
        n = counts[category]
        pct = (duration_ms / turn_duration_ms * 100) if turn_duration_ms else 0
        print(
            f"{indent}{category:<24} {duration_ms:8d} ms  ({n} call{'s' if n != 1 else ''}, {pct:5.1f}%)"
        )

    if turn_duration_ms:
        other_ms = max(turn_duration_ms - accounted_ms, 0)
        pct = other_ms / turn_duration_ms * 100
        # Time inside the turn not attributable to any streamed item: mostly
        # hidden reasoning-token computation plus network/queueing latency.
        print(f"{indent}{'other / hidden compute':<24} {other_ms:8d} ms  ({pct:5.1f}%)")
        print(f"{indent}{'-' * 46}")
        print(f"{indent}{'turn total':<24} {turn_duration_ms:8d} ms  (100.0%)")

    print(f"\n{indent}detail (chronological)")
    for category, label, duration_ms in entries:
        tag = category.split(":", 1)[0]
        print(f"{indent}  [{tag:<10}] {label:<48} {duration_ms:6d} ms")


async def _print_capability_manifest(codex: AsyncCodex, workspace: Path) -> None:
    """List everything the agent has to work with before a turn starts."""
    _hr("CAPABILITIES")
    print(f"  model          : {MODEL}")
    print(f"  effort         : {EFFORT or '(account default)'}")
    print(f"  sandbox        : {SANDBOX.value}")

    file_count = 0
    total_bytes = 0
    for path in workspace.rglob("*"):
        if path.is_file():
            file_count += 1
            total_bytes += path.stat().st_size
    print(
        f"  workspace      : {workspace}  ({file_count} files, {total_bytes / 1024:.1f} KB)"
    )

    try:
        mcp = await codex._client.request(
            "mcpServerStatus/list", {}, response_model=ListMcpServerStatusResponse
        )
    except Exception as exc:
        print(f"  mcp servers    : could not list ({exc})")
    else:
        if not mcp.data:
            print("  mcp servers    : none configured")
        for server in mcp.data:
            tool_names = ", ".join(sorted(server.tools)) or "(no tools)"
            print(
                f"  mcp server     : {server.name}  [{len(server.tools)} tools: {tool_names}]"
            )

    print(
        "  built-in tools : fixed by the Codex CLI + sandbox mode, not listable via this SDK"
    )


def _print_turn_report(
    label: str, thread_id: str, turn, items, usage, entries, final_response
) -> None:
    _hr(f"TURN — {label}")
    print(f"  thread id  : {thread_id}")
    print(f"  status     : {turn.status}")
    print(f"  duration   : {turn.duration_ms} ms")
    print(f"  items      : {len(items)}")
    print(
        f"  round trips: ~{_count_reasoning_steps(items)}  (model calls in the agent loop, lower bound)"
    )
    if turn.error:
        print(f"  error      : {turn.error}")

    print("\n  time breakdown")
    _print_time_breakdown(entries, turn.duration_ms, indent="    ")

    if usage:
        u = usage.total
        cached_pct = (
            (u.cached_input_tokens / u.input_tokens * 100) if u.input_tokens > 0 else 0
        )
        print(
            f"\n  tokens     : {u.total_tokens} total, {u.cached_input_tokens}/{u.input_tokens} input cached ({cached_pct:.1f}%)"
        )
        reasoning_pct = (
            (u.reasoning_output_tokens / u.output_tokens * 100)
            if u.output_tokens > 0
            else 0
        )
        print(
            f'  output     : {u.output_tokens} total, {u.reasoning_output_tokens} reasoning ({reasoning_pct:.1f}%)  <- invisible "hidden compute" tokens'
        )
        if usage.model_context_window:
            window_pct = u.total_tokens / usage.model_context_window * 100
            print(
                f"  context    : {u.total_tokens}/{usage.model_context_window} of the model's context window ({window_pct:.1f}%)"
            )

    print("\n  response")
    for line in (final_response or "(no final response)").splitlines():
        print(f"    {line}")


def load_api_key() -> str:
    env_file = HERE / "backend" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


async def main() -> None:
    prompt = DEFAULT_PROMPT

    api_key = load_api_key()
    if not api_key:
        sys.exit("OPENAI_API_KEY not set (environment or backend/.env)")

    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    config = CodexConfig(env={**os.environ, "CODEX_HOME": str(CODEX_HOME)})

    print(f"workspace : {WORKSPACE}")
    print(f"prompt    : {prompt}")
    print("working…  (one turn is the agent's full loop, so this takes a while)")

    process_timings: list[tuple[str, float]] = []

    async with AsyncCodex(config) as codex:
        t0 = time.perf_counter()
        await codex.login_api_key(api_key)
        t1 = time.perf_counter()
        process_timings.append(("login_api_key", t1 - t0))

        # A thread is the conversation. We start a fresh one and never come back
        # to it. `workspace_write` lets the agent edit files under cwd but not
        # outside it, and it can't reach the network.
        thread = await codex.thread_start(
            cwd=str(WORKSPACE),
            sandbox=SANDBOX,
            model=MODEL,
        )
        t2 = time.perf_counter()
        process_timings.append(("thread_start", t2 - t1))

        await _print_capability_manifest(codex, WORKSPACE)

        turn, items, usage, final_response, entries = await _run_turn_with_breakdown(
            thread, prompt, effort=EFFORT
        )
        t3 = time.perf_counter()
        process_timings.append(("turn 1 (thread.turn)", t3 - t2))

        _print_turn_report(
            "1 (new thread)", thread.id, turn, items, usage, entries, final_response
        )

        thread2 = await codex.thread_resume("019fee85-0ef7-7d31-9f88-d72cb7924613")
        t4 = time.perf_counter()
        process_timings.append(("thread_resume", t4 - t3))

        (
            turn2,
            items2,
            usage2,
            final_response2,
            entries2,
        ) = await _run_turn_with_breakdown(
            thread2,
            "change it to a toast notification which supports different positions, have it default to bottom center of page, also make it have multiple colour options, default it to a rainbow colour",
            effort=EFFORT,
        )
        t5 = time.perf_counter()
        process_timings.append(("turn 2 (thread.turn)", t5 - t4))

        _print_turn_report(
            "2 (resumed thread)",
            thread2.id,
            turn2,
            items2,
            usage2,
            entries2,
            final_response2,
        )

        _hr("PROCESS TIMING (wall clock, whole script)")
        grand_total = t5 - t0
        for label, dur in process_timings:
            pct = (dur / grand_total * 100) if grand_total > 0 else 0
            print(f"  {label:<22} {dur * 1000:8.1f} ms  ({pct:5.1f}%)")
        print(f"  {'-' * 46}")
        print(f"  {'total':<22} {grand_total * 1000:8.1f} ms  (100.0%)")


if __name__ == "__main__":
    asyncio.run(main())
