import type { GenerateResult, Provider } from "../types.ts";
import { AppError } from "../errors.ts";

/**
 * Configurable mock. One provider that simulates the outcomes the handler must
 * survive — selected via AI_PROVIDER=mock (local dev / CI) or injected directly
 * in unit tests. (Network-timeout behavior is tested at the HTTP layer.)
 */
export interface MockConfig {
  /** Text to return on success (default: a placeholder change). */
  text?: string;
  /** Return empty output — exercises the non-empty check. */
  empty?: boolean;
  /** Reject — exercises the 500 error path. */
  throwBefore?: boolean;
}

export function createMockProvider(config: MockConfig = {}): Provider {
  const fail = () => Promise.reject(new AppError("mock_error", "mock configured to throw"));
  return {
    id: "mock",
    generate(): Promise<GenerateResult> {
      if (config.throwBefore) return fail();
      return Promise.resolve({
        text: config.empty ? "" : (config.text ?? "// mock generated change"),
        usage: { inputTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0 },
      });
    },
    warm(): Promise<void> {
      if (config.throwBefore) return fail();
      return Promise.resolve();
    },
  };
}
