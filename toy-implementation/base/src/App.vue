<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="border-b border-slate-200 bg-white">
      <nav class="mx-auto flex max-w-2xl gap-4 px-6 py-3 text-sm">
        <RouterLink to="/" class="hover:text-slate-500" active-class="font-semibold">Home</RouterLink>
        <RouterLink to="/tasks" class="hover:text-slate-500" active-class="font-semibold">Tasks</RouterLink>
      </nav>
    </header>
    <main class="mx-auto max-w-2xl px-6 py-8">
      <RouterView />
    </main>
  </div>
</template>
