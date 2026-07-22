// Transport-only tests: method routing, body decoding, and the AppError → 500 /
// result → 200 mapping. Domain behavior is covered in pipeline_test.ts.

import { assertEquals } from "@std/assert";
import { createHandler } from "../generate/index.ts";
import { createMockProvider, type MockConfig } from "../_shared/providers/mock.ts";

function handlerWith(mock: MockConfig) {
  return createHandler({ provider: createMockProvider(mock) });
}

function post(body: unknown): Request {
  return new Request("http://localhost/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

const VALID = { messages: [{ role: "user", content: "add a button" }] };

Deno.test("handler: result → 200 with text", async () => {
  const res = await handlerWith({ text: "done" })(post(VALID));
  assertEquals(res.status, 200);
  assertEquals((await res.json()).text, "done");
});

Deno.test("handler: pipeline AppError → 500 with flattened message", async () => {
  const res = await handlerWith({ empty: true })(post(VALID));
  assertEquals(res.status, 500);
  assertEquals((await res.json()).error, "provider returned empty output");
});

// Full chain: a throw originating in the ADAPTER must survive the pipeline
// (which has no try/catch) and reach the handler's catch as a 500.
Deno.test("handler: adapter throw propagates through pipeline → 500", async () => {
  const res = await handlerWith({ throwBefore: true })(post(VALID));
  assertEquals(res.status, 500);
  assertEquals((await res.json()).error, "mock configured to throw");
});

Deno.test("handler: non-JSON body → 500", async () => {
  const req = new Request("http://localhost/generate", { method: "POST", body: "not json" });
  const res = await handlerWith({})(req);
  assertEquals(res.status, 500);
  assertEquals((await res.json()).error, "body must be valid JSON");
});

Deno.test("handler: GET → 405", async () => {
  const res = await handlerWith({})(new Request("http://localhost/generate", { method: "GET" }));
  assertEquals(res.status, 405);
  await res.body?.cancel();
});

Deno.test("handler: OPTIONS preflight → 204 with CORS", async () => {
  const res = await handlerWith({})(new Request("http://localhost/generate", { method: "OPTIONS" }));
  assertEquals(res.status, 204);
  assertEquals(res.headers.get("Access-Control-Allow-Origin"), "*");
  await res.body?.cancel();
});
