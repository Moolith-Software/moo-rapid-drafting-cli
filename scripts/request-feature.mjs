#!/usr/bin/env node
// End-to-end smoke test of the generate edge function against a real codebase.
//
//   read toy-model/ → serialize (sorted) → POST /generate → parse {files,deletes}
//   → copy toy-model/ to toy-model-generated/ → apply the change
//
// Usage:
//   node scripts/request-feature.mjs                    # built-in feature request
//   node scripts/request-feature.mjs "add a dark mode toggle"
//
// Env:
//   FUNCTION_URL   default http://localhost:54321/functions/v1/generate
//   FUNCTION_TOKEN bearer token (needed for a deployed function, not for `serve`)

import { readFile, writeFile, mkdir, rm, readdir, cp } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SOURCE = path.join(ROOT, "toy-model");
const TARGET = path.join(ROOT, "toy-model-generated");

const FUNCTION_URL =
  process.env.FUNCTION_URL ?? "http://localhost:54321/functions/v1/generate";

// Ignored when snapshotting the codebase — the model never sees these.
const SKIP_DIRS = new Set(["node_modules", "dist", ".git"]);
const SKIP_FILES = new Set(["package-lock.json", "bun.lockb", ".DS_Store"]);

const DEFAULT_FEATURE = `Add a toast notification system to the app.

- A Pinia store \`src/stores/toasts.ts\` holding a list of toasts, with \`push({ message, type })\`
  (type is 'success' | 'error' | 'info') and \`dismiss(id)\`. Each toast auto-dismisses after 3 seconds.
- A \`src/components/ToastItem.vue\` presenting a single toast: colour-coded left border and icon per
  type, the message, and a dismiss button.
- A \`src/components/ToastContainer.vue\` that stacks the active toasts in the bottom-right corner,
  fixed position, animated in and out with Vue's <TransitionGroup>.
- Mount the container once in \`src/App.vue\` so it is available on every page.
- Wire it up on the Tasks page: adding a task pushes a success toast, removing a task pushes an info
  toast, and submitting an empty task pushes an error toast.

Keep it accessible (aria-live on the container) and match the existing slate/Tailwind visual style.`;

/** Recursively snapshot a directory into a { path -> content } map, POSIX paths. */
async function snapshot(dir, base = dir) {
  const out = {};
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      Object.assign(out, await snapshot(path.join(dir, entry.name), base));
    } else if (entry.isFile() && !SKIP_FILES.has(entry.name)) {
      const abs = path.join(dir, entry.name);
      const rel = path.relative(base, abs).split(path.sep).join("/");
      out[rel] = await readFile(abs, "utf8");
    }
  }
  return out;
}

/**
 * Deterministic serialization: paths SORTED, fixed delimiters. The cache prefix
 * depends on this being byte-identical between calls (PLAN.md §3).
 */
function serialize(files) {
  return Object.keys(files)
    .sort()
    .map((p) => `=== FILE: ${p} ===\n${files[p]}`)
    .join("\n\n");
}

/** Models like to wrap JSON in ``` fences despite instructions. Tolerate it. */
function parseResponse(text) {
  const fenced = text.match(/```(?:json)?\s*\n([\s\S]*?)\n```/);
  const body = fenced ? fenced[1] : text;
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start === -1 || end === -1) {
    throw new Error(`no JSON object in model output:\n${text.slice(0, 500)}`);
  }
  return JSON.parse(body.slice(start, end + 1));
}

async function main() {
  const feature = process.argv[2] ?? DEFAULT_FEATURE;

  if (!existsSync(SOURCE)) throw new Error(`missing source app: ${SOURCE}`);

  const files = await snapshot(SOURCE);
  const codebase = serialize(files);
  console.log(
    `codebase: ${Object.keys(files).length} files, ${(codebase.length / 1024).toFixed(1)} KB`,
  );
  console.log(`POST ${FUNCTION_URL}`);

  const started = Date.now();
  const res = await fetch(FUNCTION_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(process.env.FUNCTION_TOKEN
        ? { authorization: `Bearer ${process.env.FUNCTION_TOKEN}` }
        : {}),
    },
    body: JSON.stringify({
      messages: [
        // stable prefix — the cacheable half
        {
          role: "user",
          content: `Here is the current application source.\n\n${codebase}`,
          cacheable: true,
        },
        // volatile — the actual ask
        { role: "user", content: `Feature request:\n\n${feature}` },
      ],
    }),
  });

  const payload = await res.json();
  const secs = ((Date.now() - started) / 1000).toFixed(1);

  if (res.status !== 200) {
    console.error(`\n✗ ${res.status} after ${secs}s: ${payload.error}`);
    process.exit(1);
  }

  console.log(`← 200 in ${secs}s`, payload.usage ?? "(no usage)");

  const change = parseResponse(payload.text);
  const changed = change.files ?? {};
  const deletes = change.deletes ?? [];

  // Rebuild the target as a clean copy of the base, then apply the change.
  await rm(TARGET, { recursive: true, force: true });
  await cp(SOURCE, TARGET, {
    recursive: true,
    filter: (src) => !SKIP_DIRS.has(path.basename(src)),
  });

  for (const [rel, content] of Object.entries(changed)) {
    const abs = path.join(TARGET, rel);
    if (!abs.startsWith(TARGET + path.sep)) {
      throw new Error(`refusing path outside target: ${rel}`);
    }
    await mkdir(path.dirname(abs), { recursive: true });
    await writeFile(abs, content, "utf8");
    console.log(`  ${rel in files ? "edit  " : "create"} ${rel}`);
  }
  for (const rel of deletes) {
    const abs = path.join(TARGET, rel);
    if (!abs.startsWith(TARGET + path.sep)) continue;
    await rm(abs, { force: true });
    console.log(`  delete ${rel}`);
  }

  await writeFile(
    path.join(TARGET, "FEATURE_REQUEST.md"),
    `# Feature request sent to the generate function\n\n${feature}\n`,
    "utf8",
  );

  console.log(`\n✓ applied to toy-model-generated/`);
  console.log(`  cd toy-model-generated && npm install && npm run dev`);
  console.log(`  diff:  diff -ru toy-model toy-model-generated`);
}

main().catch((e) => {
  console.error(`\n✗ ${e.message}`);
  process.exit(1);
});
