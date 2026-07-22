import type { GenerateRequest, GenerateResult, Provider } from "../_shared/types.ts";
import { AppError } from "../_shared/errors.ts";
import { verifyRequest } from "../_shared/verify.ts";
import { activePrompt } from "../_shared/prompts/index.ts";

/**
 * The per-request sequence: verify → inject the active system prompt →
 * generate → non-empty check.
 *
 * Transport-agnostic by design: it knows nothing about Request/Response or
 * status codes, and signals failure by THROWING a typed AppError. Choosing an
 * HTTP status is the adapter's job (generate/index.ts). This is where extra
 * steps accrete later (a server-side warm() call, response parsing, provider
 * fallback) without the endpoint growing.
 */
export async function runGenerate(
  input: unknown,
  provider: Provider,
): Promise<GenerateResult> {
  const gen = verifyRequest(input);

  // Inject the active system prompt as the cacheable first message.
  const providerReq: GenerateRequest = {
    model: gen.model,
    messages: [
      { role: "system", content: activePrompt.system, cacheable: true },
      ...gen.messages,
    ],
  };

  const result = await provider.generate(providerReq);

  if (!result.text) {
    throw new AppError("empty_result", "provider returned empty output");
  }
  return result;
}
