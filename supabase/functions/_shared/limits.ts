// OUR limits are the source of truth — enforced before any provider call, so
// behavior is identical regardless of which provider AI_PROVIDER selects. We
// never discover a limit by parsing a provider-specific error.
//
// First-pass numbers from provider math (~3.5 chars/token, ~80K-token request
// budget). See PLAN.md §3. Tune here; nothing else references raw numbers.

export const LIMITS = {
  /** Rough code tokenization used to derive the byte budget below. */
  charsPerToken: 3.5,
  /** Total per-request token budget (well under every provider's window). */
  maxRequestTokens: 80_000,
  /** Byte proxy for the token budget — the edge function's total-size backstop. */
  maxRequestBytes: 280_000,
  /** Our output cap; maps to each provider's max_tokens / max_completion_tokens. */
  maxOutputTokens: 16_000,
  /** Per-generate-call timeout. */
  timeoutMs: 120_000,

  // ── Files-map limits (enforced by the orchestrator in M3; the source of
  //    truth lives here). The edge function backstops total size via
  //    maxRequestBytes since the codebase travels inside the messages.
  maxCodebaseBytes: 200_000,
  maxFileBytes: 50_000,
  maxFileCount: 100,

  /** Concurrent run slots (orchestrator queue, M3). */
  runConcurrency: 4,
} as const;
