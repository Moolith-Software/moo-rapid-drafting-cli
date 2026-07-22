import { assertEquals, assertStringIncludes } from "@std/assert";
import { ACTIVE_PROMPT_VERSION, activePrompt, PROMPTS } from "../_shared/prompts/index.ts";

// Note: an unknown ACTIVE_PROMPT_VERSION is a compile error (PromptVersion is
// keyof typeof PROMPTS), so there's no runtime "unknown version" case to test.

Deno.test("prompts: activePrompt is the entry at ACTIVE_PROMPT_VERSION", () => {
  assertEquals(activePrompt, PROMPTS[ACTIVE_PROMPT_VERSION]);
});

Deno.test("prompts: active prompt carries a name and system text", () => {
  assertEquals(activePrompt.name, "Initial version");
  assertStringIncludes(activePrompt.system, "Vue 3");
});

Deno.test("prompts: versions are selected by key", () => {
  assertEquals(PROMPTS["1.0"].name, "Initial version");
});
