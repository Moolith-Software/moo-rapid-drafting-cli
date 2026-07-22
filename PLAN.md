# Rapid Prototyping Tool — Architecture Plan

A desktop tool (Tauri 2 + Vue 3 + Pinia + Supabase) that helps people rapidly
iterate on frontend features by having AI build them fast, exploring breadth
(many candidate directions) and depth (polishing one), so you can pick the
right set and know exactly what's being built.

Stack: **Tauri 2** desktop (multiple build targets) · **Vue 3 + Pinia** ·
**Supabase** (edge functions) · **Bun + Vite** (local run toolchain).

---

## 1. The core loop

```
container (a runnable web app)
   → feature request / change
   → AI implements the change
   → run it locally (build + mount)
   → if it fails, feed the error back and retry (up to 3×)
   → preview the result
```

- **Parallel by default** — many feature requests run at once (breadth).
- **Fast turnaround** — minimize the wait per change.
- **Provider-agnostic** — swap AI models via config, no app-code changes.

States per change: `queued → working → testing → completed | failed`.

```
queued → working → testing → completed
            ↑          │
            └──────────┘   (run failed, attempts < 3: re-generate — holds its slot)
                       │
                       └→ failed   (3 attempts exhausted, or hard error)

  (releases its run slot on completed | failed → next queued item starts)
```

- **queued** — accepted, waiting for a run slot (behind the concurrency cap)
- **working** — has a slot, generating the change
- **testing** — building + mounting
- **completed / failed** — terminal; releases the slot

---

## 2. Layers

The system is three layers. The **provider layer never changes** when anything
above it changes — that's the design invariant.

```
┌─ ORCHESTRATOR (Vue frontend) ── owns state, the tree, the 3-loop, caching
│    • holds the files map / container manifest
│    • assembles the request, calls the provider (edge fn)
│    • invokes Tauri to run; hosts the preview iframe
└──────────────┬────────────────────────────┬───────────────────────────────┘
     provider  │                     Tauri   │
   (edge fn)   ▼                    invoke() ▼
┌─ PROVIDER LAYER ───────────┐   ┌─ RUN HARNESS (Tauri Rust + Bun/Vite) ──────┐
│  messages in → text out    │   │  write files → vite build → preview:// URL │
│  knows NOTHING about code  │   │  capture build + runtime errors            │
└────────────────────────────┘   └────────────────────────────────────────────┘
```

---

## 3. Provider abstraction (BUILDABLE NOW)

Thin, stateless, provider-agnostic. One job: **turn messages into text**,
with our own limits, timeout, error-flattening, and a non-empty check.
Runs inside a **Supabase edge function** (TypeScript / Deno).

### Interface

```ts
interface Provider {
  readonly id: string;                            // "anthropic" | "openai" | "mock"
  generate(req: GenerateRequest): Promise<GenerateResult>;
  warm(req: GenerateRequest): Promise<void>;      // pre-write the cache; returns nothing
}

type Role = "system" | "user" | "assistant";

interface Message {
  role: Role;
  content: string;
  cache?: boolean;          // marks a stable/cacheable segment (system + codebase)
}

interface GenerateRequest {
  model?: string;           // optional → provider default
  messages: Message[];      // non-empty; multi-turn ready (interaction = append)
}

interface GenerateResult {
  text: string;
  usage?: { inputTokens?: number; outputTokens?: number; cacheReadTokens?: number };
}
```

- **`messages[]`, not a prompt string** — so refinement (depth) and future
  interaction are additive: "interact" = append a message and re-send. V1 is a
  conversation of length one.
- **`cache` flag** — orchestrator marks the stable prefix (`[system][codebase]`).
  Each provider translates to its native mechanism (Anthropic `cache_control`
  breakpoint; OpenAI automatic prefix caching; mock ignores). Volatile feature
  request is unmarked.
- **`warm()`** — writes the cache without generating output, so parallel breadth
  gets N cache reads instead of N writes. (Cache is only readable after the first
  write responds; warming first is what makes parallel caching actually work.)

### Registry (env-driven swap)

`AI_PROVIDER` (Supabase secret) selects the provider. The handler calls
`provider.generate()` without knowing which one it got — swapping models is an
env change, zero app-code change.

```
AI_PROVIDER   = "anthropic" | "openai" | "mock"
ANTHROPIC_API_KEY = ...
OPENAI_API_KEY    = ...
```

### Providers

- **Anthropic** — Messages API (`claude-opus-4-8` default for code-gen quality),
  raw `fetch`, maps `cache: true` → `cache_control` on the last stable block.
- **OpenAI** — Chat Completions, raw `fetch`, relies on automatic prefix caching.
- **Mock** — **configurable**, for tests + local/offline dev. Config drives every
  edge case the real providers can throw:

  | Mock config | Exercises |
  |---|---|
  | emit normal text | happy path |
  | emit empty text | the non-empty check |
  | throw before returning | pre-call failure → 500 |
  | hang | the 2-min timeout |

  Selected via `AI_PROVIDER=mock` (local dev / CI) **or** injected directly into
  the handler (unit tests).

### Handler guarantees (edge function)

1. **Validate + normalize** the request against the contract (below) → reject
   malformed input.
2. **Timeout: 2 minutes** (`AbortController` kills the upstream request).
3. **No provider-call retries** — the edge function does not silently re-hit the
   provider on a transient failure; the user retries manually. (Distinct from the
   orchestrator's 3× self-correction loop in §4, which lives in the FE — the edge
   function is stateless and single-shot: one `generate` per call.)
4. **Non-empty check** — simple `result.text.length > 0` sanity check on success.
5. **Flat errors** — everything normalizes to **200** (result) or **500**
   (flattened error message). No provider-specific error shapes reach the frontend.
6. **No token streaming** — synchronous request/response. Coarse states live in
   the orchestrator, not the wire.

### Request contract + our own limits

Validated at the **edge-function entry** (backstop) and mirrored **client-side**
(fast feedback). **Our limits are the source of truth; providers are downstream.**

Validate / normalize:
- `messages` non-empty, valid roles, non-empty content
- files map: path count ≤ cap, per-file ≤ cap, total ≤ cap, **text only**
- **paths sorted + deterministic serialization** (required — or caching breaks)

Limits (first pass; provider math, ~3.5 chars/token, ~80K-token request budget):

| Limit | Value | Notes |
|---|---|---|
| Codebase input | ~200KB (~58K tokens) | the cacheable half |
| Per file | ~50KB | |
| File count | ~100 | |
| Output (`max_tokens`) | 16K tokens | maps to each provider's param |
| Timeout | 2 min | ours |
| Retries | none / manual | ours |
| Run concurrency | 3–4 run slots (queue) | ours — gates the whole run (generate + build); also throttles concurrent provider calls. Excess requests sit in `queued`. |

> **Risk (noted):** ~200KB is generous for a minimal frontend prototype, but as
> the codebase grows past it the cap rejects real work. That's the signal to build
> scaling strategies (relevance selection / manifest+read / diff). Caching
> mitigates *cost* of a large base, not *context/latency*. Deferred, gated by an
> explicit limit rather than a surprise.

### Versioned prompts

A version-controlled `prompts/` — an array of objects keyed by version (`"1.0"`),
prompt text configurable, looked up by version. Seed with a v1.0 "implement this
frontend feature; return full contents of any changed/created files" prompt.

### File layout (edge function)

```
supabase/functions/
  _shared/
    types.ts          // Provider, GenerateResult, Env (+ re-exports wire types)
    contract.ts       // declarative Zod schema for the wire request
    verify.ts         // runs the contract → throws AppError or returns typed
    config.ts         // ProviderId + one shared ProviderConfig + default models
    limits.ts         // our own limits config
    errors.ts         // AppError → flattened 200 | 500
    prompts/index.ts  // versioned prompts; ACTIVE_PROMPT_VERSION picked server-side
    providers/
      anthropic.ts    // @anthropic-ai/sdk, Messages API + cache_control mapping
      openai.ts       // openai SDK, RESPONSES API (not Chat Completions), store:false
      mock.ts         // configurable (text | empty | throw)
      registry.ts     // AI_PROVIDER → provider (reads env inline)
  generate/
    index.ts          // HTTP adapter: routing, body decode, AppError → 200 | 500
    pipeline.ts       // per-request sequence: verify → inject prompt → generate
  tests/
    *_test.ts         // deno test, uses the mock
```

---

## 4. Orchestrator (design sketch — client-side, Vue)

Owns state and the loop. **Client holds all state** (no table; synchronous;
retry on failure/refresh — fragility accepted).

```
files map = current node
attempt = 1
loop:
  change  = await callEdgeFn(messages)              // provider, ≤2 min
  merge change → files map                          // model returns FULL changed files
  result  = await invoke("run_build", {runId, files})  // Rust → vite, ≤60s
  if !result.ok        → messages.push(result.errors); attempt<3 ? (attempt++, continue) : FAILED
  runtime = await mountAndWatch(result.previewUrl)  // iframe bootstrap
  if runtime.errors    → messages.push(runtime.errors); attempt<3 ? (attempt++, continue) : FAILED
  → COMPLETED
```

- **Apply contract:** model returns the **full contents** of any file it
  changes/creates (+ optional deletions). Full-file replacement > diffs (models
  malform diffs; bad output just fails to build → loop retries).
  - *Tradeoff (known):* full files cost more **output** tokens than diffs. Mitigated
    by returning only *changed* files (not the whole codebase) and by the 16K
    output cap (an over-large change hits the cap → fails → retries, signalling
    it's too big for one shot). Revisit with diffs / a targeted edit tool when
    files get large — same trigger as the deferred codebase-size problem.
- **Breadth = parallel** independent runs; each is its own node + iframe.
- **Depth = refinement** — the prior state becomes the base, follow-up appended.
- **No model clarifying questions** — one-shot per turn; user retries/refines.
- **Queue** — cap concurrent **run slots** (3–4) even if the user fires 10; excess
  requests sit in `queued` and drain as slots free. A run holds its slot through
  the whole 3-loop, releasing it on `completed | failed`.

### Container manifest + files map

```ts
interface ContainerManifest {
  id: string; name: string;
  runtime: "vue3-vite-bun";
  entry: "src/main.ts";
  files: Record<string, string>;   // path → content = the state the model sees/edits
}
```

One `path → content` object end to end: FE holds it → orchestrator serializes it
(sorted) as the cacheable prompt half → model returns changed files → merge → hand
to run harness.

---

## 5. Run harness (design sketch — Tauri Rust + Bun/Vite)

Delegate the heavy lifting (SFC compile, bundling, deps, error formatting) to
**real Vite via a child process**. The only hand-built piece is a ~20-line iframe
error bootstrap.

### Tauri commands

```
ensure_runtime()                         // one-time: install fixed deps (Bun)
run_build(run_id, files) -> RunResult    // write, vite build, capture, ≤60s
cleanup_run(run_id)
RunResult { ok, errors: [{stage:"build"|"runtime", message, location?}], previewUrl? }
```

### Workspace strategy

Template dir provisioned once (= the shell + installed deps):
```
template/
  node_modules/    ← fixed deps, installed ONCE via Bun (or bundled as sidecar)
  package.json  vite.config.ts  tailwind/postcss/tsconfig
  index.html       ← error-capture bootstrap baked in
```
Per run (ephemeral, parallel-safe):
```
runs/<run_id>/
  node_modules → symlink to template/node_modules   ← no per-run install
  (config copied)  src/** (files map written)  dist/ (build output)
```
Symlinked `node_modules` = a "run" is just a build, never an install. That's what
makes parallel breadth cheap.

### Runtime

- **Bun** as the runtime/sidecar — single portable binary, faster cold start per
  spawned build, faster installs. Run **Vite under Bun** (`bun run vite build`).
  Risk (bounded): validate the fixed toolchain builds under Bun once; only revisit
  when adding a dependency.
- **V1 Node/Bun provisioning:** require it present; `ensure_runtime()` installs
  the fixed deps once into the shared template. (Later: bundle Bun + `node_modules`
  as a Tauri sidecar for zero setup.)

### Run → preview → error capture

- `vite build` → static `dist/` → **`preview://<run_id>/…`** custom protocol,
  loaded in a **sandboxed iframe** (clean origin, no local HTTP server).
- Build errors come from Vite (real, structured). Runtime errors come from the
  **baked-in bootstrap** in `index.html`: `window.onerror`, `unhandledrejection`,
  Vue `app.config.errorHandler`, + a `mounted-ok` heartbeat (with timeout).

---

## 6. The shell (`simple-vue3-shell`)

Same artifact three ways: **seed state** (root node), **vite template**, and
**dev fixture** for the loop. Minimal but **runnable-green out of the box** (root
node starts in `completed`).

```
index.html            ← error-capture bootstrap baked in
package.json          ← fixed deps: vue, pinia, vue-router, tailwind
vite.config.ts  tailwind.config.js  postcss.config.js  tsconfig.json
src/
  main.ts             ← createApp + pinia + router + mount
  App.vue             ← layout + <RouterView>
  assets/main.css     ← tailwind directives
  router/index.ts
  stores/             ← one example store
  pages/Home.vue
  components/          ← a couple of core components
  composables/  utils/  mocks/   ← may be empty; folder scaffolding is fine
```

Giving the model a working skeleton (edit, not scaffold) → far fewer one-shot
failures.

---

## 7. Caching model

- **Prompt caching** = cost/latency optimization on the shared prefix
  (`[system][codebase]`). Maps onto **breadth**: N parallel changes share one base
  → 1 write, N−1 reads. **Warm the base first**, then fan out.
- Does **not** map onto **depth** (each new state = new prefix = new write) and is
  **not** a semantic diff.
- The **state/diff tree** (how changes compose across branches) lives in the
  **client state**, not the model. Two different mechanisms — keep them separate.

---

## 8. Explicitly deferred / risks

- **Codebase size scaling** — full-snapshot has a ~200KB ceiling; relevance
  selection / manifest+read / diff-based prompting are later. Gated by the cap.
- **Persistence** — no Supabase table / Realtime for now; client holds state,
  retries on failure. Add durable runs later if fragility bites.
- **Closed-loop for breadth** — breadth stays open (fast, disposable); the 3-loop
  self-correction is where it matters (depth/polish).
- **Model clarifying questions** — not built; one-shot + retry only.
- **Bun edge cases** — bounded to dependency additions; validate per addition.

---

## 9. Build order

1. **M1 — Provider abstraction** (this doc §3): edge function, contract + limits,
   Anthropic + OpenAI + configurable mock, versioned prompts, unit tests. *The
   buildable piece; validate the abstraction against two real APIs + mock.*
   ✅ **DONE** — `supabase/functions/`, 36 passing tests (`npm run test:functions`).
   Deno managed as an npm devDependency (monorepo: npm-based FE + Deno functions).
2. **M2 — Shell + run harness** (§5, §6): `simple-vue3-shell`, Bun/Vite,
   Tauri `run_build` / `ensure_runtime`, `preview://`, error bootstrap.
3. **M3 — Orchestrator loop** (§4): 3-loop, states, files map, preview iframe,
   build queue.
4. **M4 — UI**: breadth board, depth drill-in, selection.
```
