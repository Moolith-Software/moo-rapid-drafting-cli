# Dev docs

A high-level, human-readable overview of what the rapid drafting tool is and how it works **today**. It's the baseline that changes start from: enough for a person or an agent to understand the application, not a detailed spec. A change made through OpenSpec may challenge or replace what's described here; when it does, these docs are updated to match as part of the OpenSpec archive step, once the change is complete and settled.

| File | What it holds |
|---|---|
| `proposal.md` | What the system is, who it's for, what it does today, what it doesn't do yet |
| `design.md` | How it works: layout, data flow, data model, API shape, errors, invariants, edge cases, frontend, testing, risks |
| `reviewing.md` | Guidelines for the AI reviewer that checks each milestone before the developer reviews it |

## How this fits with OpenSpec

| Where | What it holds |
|---|---|
| `dev-docs/` | the high-level design: what the system is and how it works, in prose and tables |
| `openspec/specs/` | the required behavior of features added through OpenSpec, as requirements with WHEN/THEN scenarios. It started empty, so it only covers features added since |
| `openspec/changes/archive/<date>-<change>/` | each change's proposal, design, specs, tasks and decisions. History, not authority: these docs link to it instead of repeating it |

## Update rules

These docs are updated when a change is archived (`/opsx:archive`), from that change's `## Dev docs impact` section, after its delta specs are synced into `openspec/specs/`.

1. Only touch sections the change actually altered. If the impact says "None", change nothing.
2. Edit in place so each section reads as the current state, not a diff. Don't leave "previously..." notes; that's what the archive is for.
3. New invariants and edge cases get the next free `INV-` or `EC-` number. Never renumber or reuse one. A retired row stays in its table as **retired**, with a link to the change that retired it.
4. When a change covers an invariant or edge case, fill in its **Spec requirement** column as `<capability>: <requirement>` (the synced spec in `openspec/specs/`) and its **Tests (tasks)** column as `<change> <task>`, replacing "none yet". A fixed **GAP** row becomes the current behavior.
5. Add one line to the **Change log** at the bottom of each file you edited: date, change name, sections touched.
6. If something the change built contradicts these docs, fix the docs to match the code, and say so in the archive summary.

## When to add a file

Split a section out of `design.md` into its own file once changes keep editing only that section. Likely first candidates are `invariants.md` and a `glossary.md`. Add the new file to the table above when you do.
