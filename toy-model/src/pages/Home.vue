<script setup lang="ts">
import { useTasksStore } from "../stores/tasks";

const tasks = useTasksStore();
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold text-slate-900">Toy Model</h1>
    <p class="max-w-prose text-sm text-slate-600">
      A deliberately small Vue 3 + Pinia + Vue Router + Tailwind app. It exists so the
      prototyping tool has something real to change.
    </p>
    <div class="rounded-lg border border-slate-200 p-4">
      <p class="text-sm text-slate-600">
        <span class="font-semibold text-slate-900">{{ tasks.remaining }}</span>
        task<span v-if="tasks.remaining !== 1">s</span> still open.
      </p>
    </div>
  </section>
</template>
