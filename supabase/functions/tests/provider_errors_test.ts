import { assertEquals, assertInstanceOf, assertStringIncludes } from "@std/assert";
import Anthropic from "@anthropic-ai/sdk";
import OpenAI from "openai";
import { toAppError as anthropicError } from "../_shared/providers/anthropic.ts";
import { toAppError as openaiError } from "../_shared/providers/openai.ts";
import { AppError } from "../_shared/errors.ts";

Deno.test("anthropic: SDK timeout → AppError('timeout')", () => {
  const mapped = anthropicError(new Anthropic.APIConnectionTimeoutError({ message: "timed out" }));
  assertInstanceOf(mapped, AppError);
  assertEquals(mapped.code, "timeout");
  assertStringIncludes(mapped.message, "timed out after");
});

Deno.test("anthropic: SDK API error → AppError('provider_error') with status", () => {
  const mapped = anthropicError(new Anthropic.APIError(429, undefined, "rate limited", undefined));
  assertEquals(mapped.code, "provider_error");
  assertStringIncludes(mapped.message, "429");
});

Deno.test("anthropic: unknown error → AppError('provider_error')", () => {
  const mapped = anthropicError(new Error("boom"));
  assertEquals(mapped.code, "provider_error");
  assertStringIncludes(mapped.message, "anthropic: boom");
});

Deno.test("anthropic: existing AppError passes through untouched", () => {
  const original = new AppError("empty_result", "nothing");
  assertEquals(anthropicError(original), original);
});

Deno.test("openai: SDK timeout → AppError('timeout')", () => {
  const mapped = openaiError(new OpenAI.APIConnectionTimeoutError({ message: "timed out" }));
  assertEquals(mapped.code, "timeout");
  assertStringIncludes(mapped.message, "timed out after");
});

Deno.test("openai: unknown error → AppError('provider_error')", () => {
  const mapped = openaiError(new Error("boom"));
  assertEquals(mapped.code, "provider_error");
  assertStringIncludes(mapped.message, "openai: boom");
});
