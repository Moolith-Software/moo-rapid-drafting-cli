// Shared config shape for any API-backed provider. The env vars that fill it
// (and the per-provider defaults) are read in providers/registry.ts.

export type ProviderId = "anthropic" | "openai" | "mock";

export interface ProviderConfig {
  apiKey: string;
  model: string;
}
