// All internal errors carry a code + message. The handler flattens EVERYTHING
// to a 200 (success) or 500 (error) with a plain message — the frontend never
// sees provider-specific error shapes (including SDK error types).

export class AppError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
    this.name = "AppError";
  }
}

/** Flatten any thrown value (AppError, SDK error, etc.) into a short message. */
export function flatten(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
