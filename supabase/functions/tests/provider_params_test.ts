// The `cacheable` → provider-breakpoint mapping. Its failure mode is SILENT —
// a missing breakpoint just means full price forever, no error — so it needs
// explicit coverage rather than being inferred from a green request.

import { assertEquals } from "@std/assert";
import { buildParams as buildAnthropic } from "../_shared/providers/anthropic.ts";
import { buildParams as buildOpenAI } from "../_shared/providers/openai.ts";
import type { GenerateRequest } from "../_shared/types.ts";

const REQ: GenerateRequest = {
  messages: [
    { role: "system", content: "you are an engineer", cacheable: true },
    { role: "user", content: "the codebase", cacheable: true },
    { role: "user", content: "add a button", cacheable: false },
  ],
};

Deno.test("anthropic: system messages go to `system`, others to `messages`", () => {
  const p = buildAnthropic(REQ, "claude-opus-4-8", 16_000);
  assertEquals(p.system?.length, 1);
  assertEquals(p.messages.length, 2);
  assertEquals(p.model, "claude-opus-4-8");
  assertEquals(p.max_tokens, 16_000);
});

Deno.test("anthropic: cacheable system block gets a cache_control breakpoint", () => {
  const p = buildAnthropic(REQ, "m", 100);
  const block = (p.system as { cache_control?: unknown }[])[0];
  assertEquals(block.cache_control, { type: "ephemeral" });
});

Deno.test("anthropic: cacheable user message becomes a block with cache_control", () => {
  const p = buildAnthropic(REQ, "m", 100);
  const content = p.messages[0].content as { text: string; cache_control?: unknown }[];
  assertEquals(Array.isArray(content), true);
  assertEquals(content[0].text, "the codebase");
  assertEquals(content[0].cache_control, { type: "ephemeral" });
});

Deno.test("anthropic: non-cacheable message stays a plain string (no breakpoint)", () => {
  const p = buildAnthropic(REQ, "m", 100);
  assertEquals(p.messages[1].content, "add a button");
});

Deno.test("openai: system messages become `instructions`, others become `input`", () => {
  const p = buildOpenAI(REQ, "gpt-5.6-sol", 16_000);
  assertEquals(p.instructions, "you are an engineer");
  assertEquals(p.input.length, 2);
  assertEquals(p.model, "gpt-5.6-sol");
  assertEquals(p.max_output_tokens, 16_000);
});

Deno.test("openai: store is disabled (never persist codebases)", () => {
  assertEquals(buildOpenAI(REQ, "m", 100).store, false);
});
