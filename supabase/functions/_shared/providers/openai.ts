import OpenAI from "openai";
import type { GenerateRequest, GenerateResult, Provider } from "../types.ts";
import type { ProviderConfig } from "../config.ts";
import { AppError, flatten } from "../errors.ts";
import { LIMITS } from "../limits.ts";

/**
 * Normalize SDK failures into OUR error vocabulary. Without this the raw SDK
 * message leaks to the frontend and differs per provider — breaking the
 * "swap providers, identical behavior" guarantee.
 */
export function toAppError(e: unknown): AppError {
  if (e instanceof AppError) return e;
  if (e instanceof OpenAI.APIConnectionTimeoutError) {
    return new AppError("timeout", `openai request timed out after ${LIMITS.timeoutMs}ms`);
  }
  if (e instanceof OpenAI.APIError) {
    return new AppError("provider_error", `openai ${e.status ?? "error"}: ${e.message}`);
  }
  return new AppError("provider_error", `openai: ${flatten(e)}`);
}

/** OpenAI does automatic prefix caching, so `cache` flags need no translation —
 *  roles + content pass straight through. */
export function createOpenAIProvider(config: ProviderConfig): Provider {
  const client = new OpenAI({
    apiKey: config.apiKey,
    timeout: LIMITS.timeoutMs,
    maxRetries: 0,
  });

  const create = (req: GenerateRequest, maxTokens: number) =>
    client.chat.completions.create({
      model: req.model ?? config.model,
      messages: req.messages.map((m) => ({ role: m.role, content: m.content })),
      max_completion_tokens: maxTokens,
    });

  return {
    id: "openai",
    async generate(req): Promise<GenerateResult> {
      try {
        const res = await create(req, LIMITS.maxOutputTokens);
        return {
          text: res.choices[0]?.message?.content ?? "",
          usage: {
            inputTokens: res.usage?.prompt_tokens,
            cacheReadTokens: res.usage?.prompt_tokens_details?.cached_tokens,
          },
        };
      } catch (e) {
        throw toAppError(e);
      }
    },
    async warm(req): Promise<void> {
      try {
        await create(req, 1);
      } catch (e) {
        throw toAppError(e);
      }
    },
  };
}
