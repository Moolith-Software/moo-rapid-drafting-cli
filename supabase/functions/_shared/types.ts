// Internal domain types. The wire types (Message, GenerateRequest) are inferred
// from the contract schema (contract.ts) and re-exported here for convenience.

import type { GenerateRequest, Message } from "./contract.ts";
export type { GenerateRequest, Message };

/**
 * Caching instrument. `cacheReadTokens / inputTokens` is the cache hit ratio —
 * the only way to detect that prompt caching has silently stopped working (e.g.
 * a non-deterministic codebase serialization changing the cached prefix bytes).
 * `cacheWriteTokens` confirms a write actually happened, which is how we verify
 * warm() did anything. Optional because providers differ in what they report.
 *
 * IMPORTANT: `inputTokens` is NORMALIZED to the TOTAL input across providers.
 * The vendors disagree natively — Anthropic's `input_tokens` EXCLUDES cached and
 * cache-created tokens, while OpenAI's INCLUDES cached ones — so the adapters
 * reconcile it. Without that, the hit ratio means different things per provider.
 */
export interface Usage {
  /** TOTAL input tokens: fresh + cache-written + cache-read. Ratio denominator. */
  inputTokens?: number;
  /** How many were served from cache — ratio numerator. */
  cacheReadTokens?: number;
  /** How many were written to cache — confirms warm()/first-write happened. */
  cacheWriteTokens?: number;
}

export interface GenerateResult {
  text: string;
  usage?: Usage;
}

export interface Provider {
  readonly id: string;
  /** messages in → text out. Timeouts are handled by the HTTP layer, not here. */
  generate(req: GenerateRequest): Promise<GenerateResult>;
  /** Pre-write the cache (no output). Best-effort per provider. */
  warm(req: GenerateRequest): Promise<void>;
}

/** Minimal env accessor — satisfied by Deno.env, and easily mocked in tests. */
export interface Env {
  get(key: string): string | undefined;
}
