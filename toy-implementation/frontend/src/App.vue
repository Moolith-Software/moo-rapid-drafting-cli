<script setup lang="ts">
// Single page: type a feature request, run it in the background, watch status,
// then refine it. All state is a plain list of features we poll for.
import { onMounted, onUnmounted, ref } from "vue";
import { api, type Feature } from "./api";

const features = ref<Feature[]>([]);
const draft = ref("");
const busy = ref(false);
const error = ref("");

// Statuses that mean "still working" — we keep polling while any feature is here.
const ACTIVE = ["queued", "initialized", "copying", "warming", "running"];

async function refresh() {
  features.value = await api.listFeatures();
}

// Submit a new feature: initialize (creates the row + CoW workspace) then add
// (kicks off Codex in the background). We return immediately and let polling
// show progress.
async function submit() {
  const text = draft.value.trim();
  if (!text) return;
  busy.value = true;
  error.value = "";
  try {
    const feature = await api.initialize(text);
    await api.add(feature.id);
    draft.value = "";
    await refresh();
  } catch (e) {
    error.value = String(e);
  } finally {
    busy.value = false;
  }
}

// Refinement drafts, keyed by feature id.
const refineDrafts = ref<Record<number, string>>({});

// Preview: ask the backend to start a dev server, then open it in a new tab so
// the base and any feature can be compared side by side. Track "starting" state
// per target since spinning up Vite takes a moment.
const previewing = ref<Record<string, boolean>>({});

async function openPreview(key: string, start: () => Promise<{ url: string }>) {
  previewing.value[key] = true;
  error.value = "";
  try {
    const { url } = await start();
    window.open(url, key); // reuse the same tab per target on repeat clicks
  } catch (e) {
    error.value = String(e);
  } finally {
    previewing.value[key] = false;
  }
}

const previewBase = () => openPreview("base", api.previewBase);
const previewFeature = (id: number) =>
  openPreview(`feature-${id}`, () => api.previewFeature(id));

async function submitRefine(id: number) {
  const text = (refineDrafts.value[id] || "").trim();
  if (!text) return;
  try {
    await api.refine(id, text);
    refineDrafts.value[id] = "";
    await refresh();
  } catch (e) {
    error.value = String(e);
  }
}

// Poll every 1.5s while anything is active. Simple and good enough for a toy.
let timer: number | undefined;
onMounted(async () => {
  await refresh();
  timer = window.setInterval(async () => {
    if (features.value.some((f) => ACTIVE.includes(f.status))) {
      await refresh();
    }
  }, 1500);
});
onUnmounted(() => window.clearInterval(timer));

function statusClass(status: string) {
  if (status === "completed") return "done";
  if (status === "failed") return "failed";
  return "active";
}
</script>

<template>
  <main>
    <h1>Rapid Prototyping Toy</h1>
    <p class="sub">
      Describe a feature. Codex clones the base app (copy-on-write), implements it
      in the background, and reports status here.
    </p>

    <p>
      <button class="ghost" :disabled="previewing['base']" @click="previewBase">
        {{ previewing['base'] ? "Starting…" : "▶ Preview base app" }}
      </button>
    </p>

    <form class="composer" @submit.prevent="submit">
      <textarea
        v-model="draft"
        rows="4"
        placeholder="e.g. Add a dark mode toggle to the top bar"
      />
      <button type="submit" :disabled="busy || !draft.trim()">
        {{ busy ? "Starting…" : "Run feature" }}
      </button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="features.length === 0" class="empty">
      No features yet. Describe one above to get started.
    </section>

    <section v-for="f in features" :key="f.id" class="card">
      <header>
        <span class="badge" :class="statusClass(f.status)">{{ f.status }}</span>
        <strong>#{{ f.id }}</strong>
        <code class="folder">{{ f.code_folder_name }}</code>
      </header>

      <p class="request">{{ f.feature }}</p>

      <p v-if="ACTIVE.includes(f.status) && f.progress" class="progress">
        {{ f.progress }}
      </p>

      <p v-if="f.summary" class="summary">{{ f.summary }}</p>

      <ul v-if="f.file_changes.length" class="changes">
        <li v-for="c in f.file_changes" :key="c.path">
          <span class="kind" :class="c.kind">{{ c.kind }}</span> {{ c.path }}
        </li>
      </ul>

      <div v-if="f.refinements.length" class="refinements">
        <div v-for="r in f.refinements" :key="r.refinement_id" class="refinement">
          <em>Refinement {{ r.refinement_id }}:</em> {{ r.user_request }}
          <p class="summary">{{ r.summary }}</p>
        </div>
      </div>

      <p v-if="f.status === 'completed'">
        <button
          class="ghost"
          :disabled="previewing[`feature-${f.id}`]"
          @click="previewFeature(f.id)"
        >
          {{ previewing[`feature-${f.id}`] ? "Starting…" : "▶ Preview this feature" }}
        </button>
      </p>

      <form
        v-if="f.status === 'completed' || f.status === 'failed'"
        class="refine"
        @submit.prevent="submitRefine(f.id)"
      >
        <input
          v-model="refineDrafts[f.id]"
          placeholder="Refine this feature…"
        />
        <button type="submit" :disabled="!(refineDrafts[f.id] || '').trim()">
          Refine
        </button>
      </form>
    </section>
  </main>
</template>

<style>
/* Global (unscoped): keep the page light so the UI is readable in any OS theme. */
body { margin: 0; background: #f1f5f9; }
</style>

<style scoped>
main {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1rem 4rem;
  font-family: system-ui, sans-serif;
  color: #1e293b;
}
h1 { margin: 0 0 0.25rem; }
.sub { color: #64748b; margin: 0 0 1.5rem; }
.composer { display: flex; flex-direction: column; gap: 0.5rem; margin-bottom: 1rem; }
textarea, input {
  width: 100%;
  padding: 0.6rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
  box-sizing: border-box;
}
button {
  align-self: flex-start;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: white;
  font: inherit;
  cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost { background: #fff; color: #2563eb; border: 1px solid #2563eb; }
.error { color: #dc2626; }
.empty { color: #94a3b8; padding: 2rem 0; text-align: center; }
.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1rem;
  margin-bottom: 1rem;
  background: #fff;
}
.card header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
.folder { color: #94a3b8; font-size: 0.8rem; margin-left: auto; }
.badge {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  color: white;
}
.badge.active { background: #f59e0b; }
.badge.done { background: #16a34a; }
.badge.failed { background: #dc2626; }
.request { margin: 0.25rem 0; }
.progress { color: #b45309; font-size: 0.85rem; font-style: italic; }
.summary { color: #334155; background: #f8fafc; padding: 0.5rem 0.75rem; border-radius: 8px; }
.changes { list-style: none; padding: 0; margin: 0.5rem 0; font-size: 0.85rem; }
.changes li { padding: 0.15rem 0; font-family: ui-monospace, monospace; }
.kind {
  display: inline-block;
  width: 3.5rem;
  font-size: 0.7rem;
  text-transform: uppercase;
}
.kind.created { color: #16a34a; }
.kind.edited { color: #2563eb; }
.kind.deleted { color: #dc2626; }
.refinements { margin: 0.5rem 0; }
.refinement { border-left: 3px solid #e2e8f0; padding-left: 0.75rem; margin: 0.5rem 0; }
.refine { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
.refine input { flex: 1; }
.refine button { align-self: stretch; }
</style>
