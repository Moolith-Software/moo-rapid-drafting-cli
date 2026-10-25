# Proposal

## What this is

A rapid drafting tool for AI-generated applications. It helps people pick the highest-value features for a product, especially the best AI features, out of everything they could build, by letting them **see** each idea working before they decide.

Instead of debating features in a doc, you draft them. Drafting is the low-stakes part: each feature is a real, running change to your app, built by an AI agent on its own copy-on-write branch with a live preview, and it's cheap enough to throw away. You can draft hundreds or thousands of features on your own machine before any of them enters a real development workflow.

## Who it's for

- Vibe coders and entrepreneurs exploring what to build.
- Product managers deciding what goes into a product.
- VPs of technology focused on AI enablement, and forward deployed engineers, who need to show what AI can do inside a specific product.
- Later, AI agents themselves (see Where it's going).

## Philosophy

- **See features, always, before deciding.** See them, then discuss them.
- **Code is temporary and disposable.** Exploring has to be cheap enough to throw away.
- **Editing and reduction matter more than adding.** The goal is the best few features, not the most.
- **The product works as one cohesive UX.** Even a single added feature should fit with the others as part of a larger experience.
- **Explore every feature.**
- **Go very deep, then refine.**
- **Get feedback from others.**
- **Always keep drafting.**

## Primitives

A few simple primitives support wide, deep and rapid exploration of the feature space:

| Primitive | What it does | Today |
|---|---|---|
| **Draft a feature** | Describe a feature; an agent builds it on its own branch of the app | Built: `POST /core/add`, one or up to 1000 at once |
| **Refine a feature** | Change a feature in place, a few times as needed, keeping its history | Built: `POST /core/refine` |
| **Branch from a feature** | Start one or more new features from an existing feature's code, to explore alternatives side by side (wide) | Built: `POST /core/add` with `parent_id` |
| **Go deep ("depth")** | Build on top of a feature with a child of it, then a child of that child, and so on (deep) | Built: `POST /core/add` with `parent_id`, repeated down the chain |
| **Combine features** | Stitch a few features together and see how they interact as a whole | Not built yet |

Branch and depth use the same mechanism: a child feature starts from its parent's code. Branching makes several children of one parent; depth makes a chain of them.

## How it works

Three capabilities make that exploration cheap and fast:

- **Copy-on-write branches.** Every feature is a copy-on-write branch of the app, aiming for O(1) per branch: the same cost whether the app has ten files or ten thousand. That's what makes hundreds or thousands of features possible on a laptop, with no cloud dependency, no per-feature cost, and no worry about running out of disk. It's also much faster and smaller than `git worktree`, which copies every file (27.7x slower at 10 GB in our benchmark). That gap grows with the app, especially with `node_modules`, which a worktree also has to reinstall, and the filesystem metadata for all those file listings grows with every copy. A branch is ready to run with its `node_modules` already in place.
- **Multiple harnesses, any provider.** The agent that builds a feature runs behind a harness interface, so the tool isn't tied to one AI vendor.
- **Preview.** Every feature that changes the frontend gets its own dev server, so you can see it in the browser and compare features side by side. A refinement hot-reloads the open tab.

## Projects

A project is the app you draft features against. Two ways to start one:

- **Import your project.** Bring an existing app; the tool prepares and sanitizes it so it works inside the tool, then builds the base every feature branches from. Planned, not built.
- **Start from a template.** Create a new project from a starter template. Later.

Today there is one built-in base app (`base/`), and every feature branches from it.

## What it does today

- Draft, refine, branch and go deep on features, through the API.
- **Preload environments** ahead of time (the intent is for the frontend to do this on hover), so cloning, AI warm-up and the preview server are already done when a request arrives.
- Keep a child's code tied to its parent: a feature that has children can't be refined, so its children never drift from the code they started from.
- Retry a failed feature by refining it, as long as it got as far as having a branch.
- Record what changed by diffing the branch on disk before and after each turn. The agent's own summary is kept only as a human-readable description.
- Report every failure as a numbered code with a short title, stored on the feature for the poller to read.
- Copy-on-write on **macOS** (APFS sparse images). The **Linux** driver (btrfs snapshots) is written but hasn't been run on a Linux machine yet.
- One harness for real use, **Codex** (OpenAI), plus a mock harness for local runs.

## What it doesn't do yet

- **Combine features**, the last primitive above.
- **Projects**: importing your own app, or starting from a template. The add-project endpoint, per-project bases and `default_project_id` aren't built, and nothing builds the base automatically yet.
- **Windows** copy-on-write. The design is open; the backend refuses to start on Windows today.
- **Other providers.** The harness interface exists, but Codex is the only real harness.
- **Feedback from others**: sharing features and collecting reactions.
- **The desktop app.** Paths are mocked to the backend folder until the Tauri shell supplies the app-data folder.
- **Cleanup.** Nothing reaps stale warm environments, old branches or idle preview servers.
- **Resource caps.** `max_ram_usage_gb` exists in settings but isn't wired in.
- **Recovery after restart.** Features that were in flight when the backend stopped stay stuck.
- **A frontend that can write.** The current UI can list and read features, but its create, refine and preview calls target endpoints that no longer exist (see design.md, Decision 11).
- **Tests.** The backend has lint, format, type, dead-code and custom-rule checks, but no test suite.

## Where it's going

- **Desktop app.** The frontend becomes a Tauri app for macOS, Windows and Linux.
- **Backend.** FastAPI today; it may become a Rust implementation with an attached TUI.
- **Two modes.** A desktop mode for people, and an **agent mode**: an agent downloads the Python or Rust binary and explores product or feature ideas end to end, perhaps overnight. By morning, out of thousands of features, it proposes the top two or three. Agents may become the main users.

## Non-goals

- A development environment. Drafting is for deciding what to build; the winning features move into a normal coding workflow afterwards.
- Automatic retries of failed AI turns. A failure is reported with a code that says what to do, and the user decides or can retry.
- Cloud hosting or per-feature billing. Everything runs on the user's own machine.

## Change log

- 2026-10-25 - initial version, caught up from the product vision and a read of the code; no change archived yet.
