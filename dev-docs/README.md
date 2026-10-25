# Dev docs

What the rapid drafting tool is and how it works **today**. OpenSpec (`openspec/`) is only for changes; these files are the current state those changes build on.

| File | What it holds |
|---|---|
| `proposal.md` | What the system is, who it's for, what it does today, what it doesn't do yet |
| `design.md` | How it works: layout, data flow, data model, API shape, errors, invariants, edge cases, frontend, testing, risks |

## Where history lives

Every change's proposal, design, specs, tasks and decisions stay in `openspec/changes/archive/<date>-<change>/`. These docs don't repeat that history. They link to the archived change instead.

Delta specs are not synced into `openspec/specs/`. They stay in the archived change as part of its record.

## Update rules

These docs are updated when a change is archived (`/opsx:archive`), from that change's `## Dev docs impact` section.

1. Only touch sections the change actually altered. If the impact says "None", change nothing.
2. Edit in place so each section reads as the current state, not a diff. Don't leave "previously..." notes; that's what the archive is for.
3. New invariants and edge cases get the next free `INV-` or `EC-` number. Never renumber or reuse one. A retired row stays in its table as **retired**, with a link to the change that retired it.
4. When a change covers an invariant or edge case, fill in its **Spec requirement** and **Tests (tasks)** columns as `<change>: <requirement>` and `<change> <task>`, replacing "none yet". A fixed **GAP** row becomes the current behavior.
5. Add one line to the **Change log** at the bottom of each file you edited: date, change name, sections touched.
6. If something the change built contradicts these docs, fix the docs to match the code, and say so in the archive summary.

## When to add a file

Split a section out of `design.md` into its own file once changes keep editing only that section. Likely first candidates are `invariants.md` and a `glossary.md`. Add the new file to the table above when you do.
