<script setup lang="ts">
defineProps<{ variant?: "primary" | "ghost" }>();
</script>

<template>
  <button
    class="rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
    :class="
      variant === 'ghost'
        ? 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
        : 'bg-slate-900 text-white hover:bg-slate-700'
    "
  >
    <slot />
  </button>
</template>
