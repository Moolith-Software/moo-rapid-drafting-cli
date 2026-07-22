import { assertEquals, assertThrows } from "@std/assert";
import { getProvider } from "../_shared/providers/registry.ts";
import { AppError } from "../_shared/errors.ts";
import type { Env } from "../_shared/types.ts";

function env(map: Record<string, string>): Env {
  return { get: (k) => map[k] };
}

Deno.test("registry: defaults to mock when unset", () => {
  assertEquals(getProvider(env({})).id, "mock");
});

Deno.test("registry: selects mock", () => {
  assertEquals(getProvider(env({ AI_PROVIDER: "mock" })).id, "mock");
});

Deno.test("registry: selects anthropic", () => {
  const p = getProvider(env({ AI_PROVIDER: "anthropic", ANTHROPIC_API_KEY: "sk-x" }));
  assertEquals(p.id, "anthropic");
});

Deno.test("registry: selects openai", () => {
  const p = getProvider(env({ AI_PROVIDER: "openai", OPENAI_API_KEY: "sk-x" }));
  assertEquals(p.id, "openai");
});

Deno.test("registry: unknown provider fails", () => {
  assertThrows(() => getProvider(env({ AI_PROVIDER: "gemini" })), AppError, "unknown AI_PROVIDER");
});
