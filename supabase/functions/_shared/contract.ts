// The declarative wire contract. This file defines the SHAPE of a valid request
// (and the inferred TS types). It does no checking itself — verify.ts runs it.

import { z } from "zod";
import { LIMITS } from "./limits.ts";

/**
 * One turn in the conversation.
 *
 * | field     | on the wire | parsed type                   | default | notes
 * |-----------|-------------|-------------------------------|---------|-------
 * | role      | required    | "system"|"user"|"assistant"    | —       | who the message is from
 * | content   | required    | string (min 1)                 | —       | the text; empty is rejected
 * | cacheable | omittable   | boolean (never undefined)      | false   | segment is STABLE across calls
 *
 * `role` — the handler injects the system prompt itself, so clients normally
 * send only `user` turns (plus `assistant` turns when replaying a conversation).
 * `system` is in the enum because this same type describes the internal request
 * the handler builds after injection.
 *
 * `content` — for the codebase message this is the serialized files map.
 *
 * `cacheable` — declares a PROPERTY of the content ("this doesn't change between
 * calls"), it does not command the provider to cache. Each adapter decides what
 * to do with it: Anthropic places a `cache_control` breakpoint, OpenAI an
 * explicit prompt-cache breakpoint. Uses .default(false), NOT .optional():
 * callers may omit it, but after verification it is ALWAYS a concrete boolean,
 * so no downstream code handles `undefined`. False is the safer default — a
 * missed `true` merely loses a cache hit, whereas a wrong `true` puts a
 * breakpoint on content that changes every call.
 */
export const MessageSchema = z.object({
  role: z.enum(["system", "user", "assistant"]),
  content: z.string().min(1),
  cacheable: z.boolean().default(false),
});

/**
 * A generate request.
 *
 * | field    | req? | type              | default                    | notes
 * |----------|------|-------------------|----------------------------|-------
 * | model    | no   | string            | provider's configured model | per-request override
 * | messages | YES  | Message[] (min 1) | —                          | the conversation, in order
 *
 * `model` — normally omitted; the model comes from ANTHROPIC_MODEL /
 * OPENAI_MODEL (or the built-in default in config.ts). It's on the wire for the
 * planned user-facing model picker.
 *
 * `messages` — order is meaningful. Total content across ALL messages must be
 * <= LIMITS.maxRequestBytes (enforced by the refinement below; this is what
 * backstops codebase size, since the codebase travels inside a message).
 */
export const GenerateRequestSchema = z
  .object({
    model: z.string().optional(),
    messages: z.array(MessageSchema).min(1),
  })
  .superRefine((req, ctx) => {
    const bytes = req.messages.reduce(
      (n, m) => n + new TextEncoder().encode(m.content).length,
      0,
    );
    if (bytes > LIMITS.maxRequestBytes) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `request content is ${bytes} bytes, exceeds limit of ${LIMITS.maxRequestBytes}`,
      });
    }
  });

// NOTE: these are the OUTPUT (post-verification) types — `cache` is always a
// boolean here. What a client may send is the input type, where `cache` is
// omittable; verify.ts is the boundary that turns one into the other.
export type Message = z.infer<typeof MessageSchema>;
export type GenerateRequest = z.infer<typeof GenerateRequestSchema>;
