# M1 — Provider abstraction (Supabase edge function)

A thin, stateless, provider-agnostic `generate` endpoint: **messages in → text
out**, with our own limits, a 2-minute timeout, a non-empty check, and 200/500
error flattening. Swap providers via the `AI_PROVIDER` env var — no code changes.

See [`../../PLAN.md`](../../PLAN.md) §3 for the design.

## Layout

```
_shared/
  types.ts            Provider, GenerateResult, Env (+ re-exports wire types)
  contract.ts         DECLARATIVE Zod schema for the wire request (+ inferred types)
  verify.ts           runs the contract against input → throws or returns typed
  config.ts           typed provider config shapes + default models (no validation)
  limits.ts           OUR limits (source of truth)
  errors.ts           AppError + flatten
  prompts/index.ts    versioned prompts; ACTIVE_PROMPT_VERSION picked here
  providers/
    anthropic.ts      @anthropic-ai/sdk, Messages API + cache_control mapping
    openai.ts         openai SDK, RESPONSES API (not Chat Completions)
    mock.ts           configurable (text | empty | throw)
    registry.ts       AI_PROVIDER → provider (reads env inline)
generate/
  index.ts            HTTP adapter: routing, body decode, AppError → 200 | 500
  pipeline.ts         per-request sequence: verify → inject prompt → generate
tests/                deno test suite (uses the mock — no keys, no network)
```

Providers use the **official SDKs** (`@anthropic-ai/sdk`, `openai`) — the client's
`timeout` option enforces our 2-min limit and `maxRetries: 0` disables retries.
Exact versions are pinned in `deno.lock`.

**OpenAI uses the Responses API**, not Chat Completions: materially better cache
utilization, better reasoning-model performance, and Chat Completions doesn't
support tool calling with reasoning models from GPT-5.4 on (which would block the
file-read tool we may need for large codebases). `store: false` is always set —
we send whole codebases and the client owns conversation state.

## Caching

`cacheable: true` marks a segment as stable; each adapter translates it:

| | Anthropic (Opus 4.8) | OpenAI (GPT-5.6+) |
|---|---|---|
| minimum to cache | 1,024 tokens | 1,024 tokens |
| control | `cache_control`, ≤4 breakpoints | explicit breakpoints, ≤4 writes |
| TTL | 5 min (1h at 2× write) | 30 min (only option) |
| write / read cost | 1.25× / 0.1× | 1.25× / discounted |
| verify via | `cache_read_input_tokens` | `input_tokens_details.cached_tokens` |

`warm()` pre-writes the cache. This matters because **a cache entry is only
readable after the first response completes** — firing N parallel requests cold
means N writes and zero reads. Warm once, then fan out.

`Usage.inputTokens` is **normalized to the total** across providers: Anthropic's
native `input_tokens` excludes cached/cache-created tokens (we sum all three),
OpenAI's already includes them. Without that the hit ratio would mean different
things per provider.

⚠️ Not yet wired: OpenAI's `prompt_cache_key` is **required on GPT-5.6+ for
reliable cache matching**. It needs the base-state ID, which doesn't exist until
the orchestrator (M3).

## Test (no keys, fast, deterministic)

```sh
cd supabase/functions
deno task test
```

Covers: contract validation, the configurable mock (incl. timeout kill),
registry provider-swap, prompt versions, timeout, and the handler's 200/500
paths + CORS.

## Run locally

```sh
# from the repo root, with the Supabase CLI:
supabase functions serve generate --env-file supabase/functions/.env.example
```

### Try it — mock (offline, no keys)

```sh
curl -s localhost:54321/functions/v1/generate \
  -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"the codebase","cache":true},
                    {"role":"user","content":"add a counter button"}]}'
# → 200 {"text":"// mock generated change", ...}
```

### Prove provider-swap

Set `AI_PROVIDER=anthropic` (+ `ANTHROPIC_API_KEY`) in your env file and re-run
the **same** curl → real generated code. Flip to `AI_PROVIDER=openai`
(+ `OPENAI_API_KEY`) → same request, same response shape, different backend.
Zero code change.

### Prove our-own-limits

Send a payload whose message content exceeds `maxRequestBytes` (~280 KB) →
clean `500 {"error":"...exceeds limit..."}`, not a provider-specific error.

## Deploy

```sh
supabase functions deploy generate
supabase secrets set AI_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-...
```
