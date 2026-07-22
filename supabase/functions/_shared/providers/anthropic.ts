import Anthropic from "@anthropic-ai/sdk";
import type { GenerateRequest, GenerateResult, Message, Provider } from "../types.ts";
import type { ProviderConfig } from "../config.ts";
import { AppError, flatten } from "../errors.ts";
import { LIMITS } from "../limits.ts";

/**
 * Map our provider-agnostic messages onto the Messages API shape, translating
 * `cacheable: true` into `cache_control` breakpoints (max 4 per request).
 * Exported for testing — this mapping's failure mode is SILENT (a missing
 * breakpoint just means full price forever, with no error).
 */
export function buildParams(
  req: GenerateRequest,
  model: string,
  maxTokens: number,
): Anthropic.MessageCreateParamsNonStreaming {
  const system: Anthropic.TextBlockParam[] = [];
  const messages: Anthropic.MessageParam[] = [];

  for (const m of req.messages as Message[]) {
    const cc = m.cacheable ? { cache_control: { type: "ephemeral" as const } } : {};
    if (m.role === "system") {
      system.push({ type: "text", text: m.content, ...cc });
    } else {
      const content = m.cacheable
        ? [{ type: "text" as const, text: m.content, ...cc }]
        : m.content;
      messages.push({ role: m.role, content });
    }
  }
  return { model, max_tokens: maxTokens, system, messages };
}

/**
 * Normalize SDK failures into OUR error vocabulary. Without this the raw SDK
 * message leaks to the frontend and differs per provider — breaking the
 * "swap providers, identical behavior" guarantee.
 */
export function toAppError(e: unknown): AppError {
  if (e instanceof AppError) return e;
  if (e instanceof Anthropic.APIConnectionTimeoutError) {
    return new AppError("timeout", `anthropic request timed out after ${LIMITS.timeoutMs}ms`);
  }
  if (e instanceof Anthropic.APIError) {
    return new AppError("provider_error", `anthropic ${e.status ?? "error"}: ${e.message}`);
  }
  return new AppError("provider_error", `anthropic: ${flatten(e)}`);
}

export function createAnthropicProvider(config: ProviderConfig): Provider {
  const client = new Anthropic({
    apiKey: config.apiKey,
    timeout: LIMITS.timeoutMs,
    maxRetries: 0,
  });
  const model = (req: GenerateRequest) => req.model ?? config.model;

  return {
    id: "anthropic",
    async generate(req): Promise<GenerateResult> {
      try {
        const msg = await client.messages.create(
          buildParams(req, model(req), LIMITS.maxOutputTokens),
        );
        const text = msg.content
          .filter((b): b is Anthropic.TextBlock => b.type === "text")
          .map((b) => b.text)
          .join("");

        // Anthropic's input_tokens EXCLUDES cached + cache-created tokens, so
        // sum all three to get the TOTAL our Usage contract promises.
        const cacheRead = msg.usage.cache_read_input_tokens ?? 0;
        const cacheWrite = msg.usage.cache_creation_input_tokens ?? 0;
        return {
          text,
          usage: {
            inputTokens: msg.usage.input_tokens + cacheRead + cacheWrite,
            cacheReadTokens: cacheRead,
            cacheWriteTokens: cacheWrite,
          },
        };
      } catch (e) {
        throw toAppError(e);
      }
    },
    async warm(req): Promise<void> {
      try {
        // max_tokens: 0 is the documented pre-warm form — writes the cache,
        // returns empty content, bills no output tokens.
        await client.messages.create(buildParams(req, model(req), 0));
      } catch (e) {
        throw toAppError(e);
      }
    },
  };
}
