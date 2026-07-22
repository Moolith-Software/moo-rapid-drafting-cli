import { assertEquals, assertThrows } from "@std/assert";
import { verifyRequest } from "../_shared/verify.ts";
import { AppError } from "../_shared/errors.ts";
import { LIMITS } from "../_shared/limits.ts";

Deno.test("verify: accepts a valid request", () => {
  const req = verifyRequest({
    model: "claude-opus-4-8",
    messages: [
      { role: "user", content: "the codebase", cacheable: true },
      { role: "user", content: "add a button" },
    ],
  });
  assertEquals(req.model, "claude-opus-4-8");
  assertEquals(req.messages.length, 2);
  assertEquals(req.messages[0].cacheable, true);
});

Deno.test("verify: model optional", () => {
  const req = verifyRequest({ messages: [{ role: "user", content: "hi" }] });
  assertEquals(req.model, undefined);
});

Deno.test("verify: cache defaults to false when omitted", () => {
  const req = verifyRequest({ messages: [{ role: "user", content: "hi" }] });
  // omittable on the wire, but never undefined after verification
  assertEquals(req.messages[0].cacheable, false);
});

Deno.test("verify: rejects non-object body", () => {
  assertThrows(() => verifyRequest("nope"), AppError);
});

Deno.test("verify: rejects empty messages", () => {
  assertThrows(() => verifyRequest({ messages: [] }), AppError);
});

Deno.test("verify: rejects missing messages", () => {
  assertThrows(() => verifyRequest({}), AppError);
});

Deno.test("verify: rejects bad role", () => {
  assertThrows(() => verifyRequest({ messages: [{ role: "robot", content: "x" }] }), AppError);
});

Deno.test("verify: rejects empty content", () => {
  assertThrows(() => verifyRequest({ messages: [{ role: "user", content: "" }] }), AppError);
});

Deno.test("verify: rejects non-boolean cache", () => {
  assertThrows(
    () => verifyRequest({ messages: [{ role: "user", content: "x", cacheable: "yes" }] }),
    AppError,
  );
});

Deno.test("verify: rejects a request over the size limit", () => {
  const big = "x".repeat(LIMITS.maxRequestBytes + 1);
  assertThrows(
    () => verifyRequest({ messages: [{ role: "user", content: big }] }),
    AppError,
    "exceeds limit",
  );
});
