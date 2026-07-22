import type { Env, Provider } from "../_shared/types.ts";
import { AppError, flatten } from "../_shared/errors.ts";
import { getProvider } from "../_shared/providers/registry.ts";
import { runGenerate } from "./pipeline.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "content-type, authorization",
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });
}

interface Deps {
  env: Env;
  provider: Provider;
}

/**
 * HTTP adapter for the generate endpoint. Owns transport concerns only: method
 * routing, decoding the body, and mapping the pipeline's result / AppError onto
 * 200 | 500. All domain logic lives in pipeline.ts.
 *
 * The provider is resolved ONCE here (composition root) rather than per request.
 */
export function createHandler(deps?: Partial<Deps>): (req: Request) => Promise<Response> {
  const env = deps?.env ?? (Deno.env as Env);
  const provider = deps?.provider ?? getProvider(env);

  return async (req: Request): Promise<Response> => {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (req.method !== "POST") return json(405, { error: "method not allowed" });

    try {
      const raw = await req.json().catch(() => {
        throw new AppError("invalid_request", "body must be valid JSON");
      });

      const result = await runGenerate(raw, provider);

      return json(200, { text: result.text, usage: result.usage });
    } catch (e) {
      return json(500, { error: flatten(e) });
    }
  };
}

if (import.meta.main) {
  Deno.serve(createHandler());
}
