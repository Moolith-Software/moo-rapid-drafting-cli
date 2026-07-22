import OpenAI from "openai";
import type { GenerateRequest, GenerateResult, Message, Provider } from "../types.ts";
import type { ProviderConfig } from "../config.ts";
import { AppError, flatten } from "../errors.ts";
import { LIMITS } from "../limits.ts";

/**
 * Map our provider-agnostic messages onto the RESPONSES API shape (not Chat
 * Completions): system messages become the top-level `instructions`, the rest
 * become `input` items. Exported for testing.
 *
 * We use Responses because it gives materially better cache utilization, better
 * reasoning-model performance, and because tool calling is unsupported in Chat
 * Completions with reasoning models from GPT-5.4 onward.
 */
export function buildParams(req: GenerateRequest, model: string, maxTokens: number) {
  const instructions: string[] = [];
  const input: OpenAI.Responses.ResponseInputItem[] = [];

  for (const m of req.messages as Message[]) {
    if (m.role === "system") {
      instructions.push(m.content);
    } else {
      input.push({ role: m.role, content: m.content });
    }
  }

  return {
    model,
    instructions: instructions.join("\n\n"),
    input,
    max_output_tokens: maxTokens,
    // Responses persists by default. We send entire codebases and the client
    // owns conversation state, so there is no reason to let them store it.
    store: false,
  };
}

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

export function createOpenAIProvider(config: ProviderConfig): Provider {
  const client = new OpenAI({
    apiKey: config.apiKey,
    timeout: LIMITS.timeoutMs,
    maxRetries: 0,
  });
  const model = (req: GenerateRequest) => req.model ?? config.model;

  return {
    id: "openai",
    async generate(req): Promise<GenerateResult> {
      try {
        const res = await client.responses.create(
          buildParams(req, model(req), LIMITS.maxOutputTokens),
        );
        return {
          text: res.output_text ?? "",
          usage: {
            // OpenAI's input_tokens already INCLUDES cached tokens, so it is
            // the total our Usage contract promises — no summing needed.
            inputTokens: res.usage?.input_tokens,
            cacheReadTokens: res.usage?.input_tokens_details?.cached_tokens,
          },
        };
      } catch (e) {
        throw toAppError(e);
      }
    },
    async warm(req): Promise<void> {
      try {
        await client.responses.create(buildParams(req, model(req), 16));
      } catch (e) {
        throw toAppError(e);
      }
    },
  };
}
