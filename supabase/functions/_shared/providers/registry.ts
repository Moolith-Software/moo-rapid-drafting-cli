import type { Env, Provider } from "../types.ts";
import { AppError } from "../errors.ts";
import { createAnthropicProvider } from "./anthropic.ts";
import { createOpenAIProvider } from "./openai.ts";
import { createMockProvider } from "./mock.ts";

/**
 * Resolve the active provider from AI_PROVIDER — the single swap point: change
 * the env var, no app-code changes. Each case builds its own config from the
 * env vars that provider needs. Defaults to the mock (fail-safe/offline).
 */
export function getProvider(env: Env): Provider {
  const id = env.get("AI_PROVIDER") ?? "mock";
  switch (id) {
    case "anthropic":
      return createAnthropicProvider({
        apiKey: env.get("ANTHROPIC_API_KEY") ?? "",
        model: env.get("ANTHROPIC_MODEL") ?? "claude-opus-4-8",
      });
    case "openai":
      return createOpenAIProvider({
        apiKey: env.get("OPENAI_API_KEY") ?? "",
        model: env.get("OPENAI_MODEL") ?? "gpt-5",
      });
    case "mock":
      return createMockProvider();
    default:
      throw new AppError("config_error", `unknown AI_PROVIDER: ${id}`);
  }
}
