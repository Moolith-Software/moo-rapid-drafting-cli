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
    anthropic.ts      @anthropic-ai/sdk + cache_control mapping (thin)
    openai.ts         openai SDK (automatic prefix caching) (thin)
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
