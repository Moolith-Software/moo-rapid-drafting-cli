// Internal domain types. The wire types (Message, GenerateRequest) are inferred
// from the contract schema (contract.ts) and re-exported here for convenience.

import type { GenerateRequest, Message } from "./contract.ts";
export type { GenerateRequest, Message };

/**
 * Caching instrument. These two are a PAIR, not independent metrics:
 * `cacheReadTokens / inputTokens` is the cache hit ratio, which is the only way
 * to detect that prompt caching has silently stopped working (e.g. a
 * non-deterministic codebase serialization changing the cached prefix bytes).
 * Both are optional because providers differ in what they report.
 */
export interface Usage {
  /** Tokens sent (system prompt + codebase + request) — the ratio denominator. */
  inputTokens?: number;
  /** How many of those were served from cache — the ratio numerator. */
  cacheReadTokens?: number;
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
