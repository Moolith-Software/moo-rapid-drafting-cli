---
name: "Review"
description: "Run the AI review loop (Codex) on the current work, a milestone or anything else, and report the findings"
---

Run the AI review loop described in the **AI review** section of `CLAUDE.md`, from step 1 to the report.

Argument from the developer, if any: $ARGUMENTS

- `adhoc`: pass `MODE=adhoc` to every `make review-round`, so the work is reviewed ad hoc even if a milestone is in progress (e.g. a hotfix).
- A change name: pass `CHANGE=<that change>` to every `make review-round`.
- `rounds=N` (combinable with the above): pass `ROUNDS=N` to every `make review-round`; 1 to 5, default 2.
- Nothing: let `make review-round` pick the mode: milestone mode for OpenSpec work in progress, ad hoc mode otherwise.

Leave every fix uncommitted, and end with the report in chat.
