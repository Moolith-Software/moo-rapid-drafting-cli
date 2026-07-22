import { assertEquals, assertRejects, assertStringIncludes } from "@std/assert";
import { runGenerate } from "../generate/pipeline.ts";
import { createMockProvider } from "../_shared/providers/mock.ts";
import { AppError } from "../_shared/errors.ts";
import type { GenerateRequest, GenerateResult, Provider } from "../_shared/types.ts";

const VALID = { messages: [{ role: "user", content: "add a button" }] };

/** A provider that records what it was asked to generate. */
function capturingProvider(text = "ok"): { provider: Provider; seen: GenerateRequest[] } {
  const seen: GenerateRequest[] = [];
  const provider: Provider = {
    id: "capture",
    generate(req): Promise<GenerateResult> {
      seen.push(req);
      return Promise.resolve({ text });
    },
    warm(): Promise<void> {
      return Promise.resolve();
    },
  };
  return { provider, seen };
}

Deno.test("pipeline: returns the provider result", async () => {
  const result = await runGenerate(VALID, createMockProvider({ text: "done" }));
  assertEquals(result.text, "done");
});

Deno.test("pipeline: injects the active system prompt as a cached first message", async () => {
  const { provider, seen } = capturingProvider();
  await runGenerate(VALID, provider);

  const sent = seen[0].messages;
  assertEquals(sent.length, 2); // injected system + the caller's message
  assertEquals(sent[0].role, "system");
  assertEquals(sent[0].cacheable, true); // marks the stable prefix for caching
  assertStringIncludes(sent[0].content, "Vue 3");
  assertEquals(sent[1].content, "add a button");
});

Deno.test("pipeline: empty output → AppError('empty_result')", async () => {
  await assertRejects(
    () => runGenerate(VALID, createMockProvider({ empty: true })),
    AppError,
    "provider returned empty output",
  );
});

Deno.test("pipeline: invalid input → AppError from verify", async () => {
  await assertRejects(
    () => runGenerate({ messages: [] }, createMockProvider()),
    AppError,
  );
});

Deno.test("pipeline: provider failure propagates", async () => {
  await assertRejects(
    () => runGenerate(VALID, createMockProvider({ throwBefore: true })),
    AppError,
    "configured to throw",
  );
});
