// Runs incoming data against the contract (contract.ts). On any mismatch it
// throws AppError("invalid_request"); on success it returns the typed request.

import { AppError } from "./errors.ts";
import { GenerateRequestSchema, type GenerateRequest } from "./contract.ts";

export function verifyRequest(input: unknown): GenerateRequest {
  const result = GenerateRequestSchema.safeParse(input);
  if (!result.success) {
    throw new AppError("invalid_request", result.error.issues.map((i) => i.message).join("; "));
  }
  return result.data;
}
