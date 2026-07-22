import { assertEquals, assertRejects } from "@std/assert";
import { createMockProvider } from "../_shared/providers/mock.ts";
import { AppError } from "../_shared/errors.ts";
import type { GenerateRequest } from "../_shared/types.ts";

// Post-verification shape: `cacheable` is always a concrete boolean.
const REQ: GenerateRequest = { messages: [{ role: "user", content: "x", cacheable: false }] };

Deno.test("mock: returns default text", async () => {
  const { text } = await createMockProvider().generate(REQ);
  assertEquals(text, "// mock generated change");
});

Deno.test("mock: returns configured text", async () => {
  const { text } = await createMockProvider({ text: "hello" }).generate(REQ);
  assertEquals(text, "hello");
});

Deno.test("mock: empty output", async () => {
  const { text } = await createMockProvider({ empty: true }).generate(REQ);
  assertEquals(text, "");
});

Deno.test("mock: throwBefore rejects", async () => {
  await assertRejects(
    () => createMockProvider({ throwBefore: true }).generate(REQ),
    AppError,
    "configured to throw",
  );
});

Deno.test("mock: warm resolves", async () => {
  await createMockProvider().warm(REQ);
});
