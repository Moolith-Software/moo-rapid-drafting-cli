<script setup lang="ts">
import { computed } from "vue";

export type ToastPosition = "top-left" | "top-center" | "top-right" | "bottom-left" | "bottom-center" | "bottom-right";
export type ToastColour = "rainbow" | "slate" | "blue" | "green" | "amber" | "red";

const props = withDefaults(defineProps<{
  message: string;
  position?: ToastPosition;
  colour?: ToastColour;
}>(), {
  position: "bottom-center",
  colour: "rainbow",
});

defineEmits<{ close: [] }>();

const positionClass = computed(() => ({
  "top-left": "top-6 left-6",
  "top-center": "top-6 left-1/2 -translate-x-1/2",
  "top-right": "top-6 right-6",
  "bottom-left": "bottom-6 left-6",
  "bottom-center": "bottom-6 left-1/2 -translate-x-1/2",
  "bottom-right": "right-6 bottom-6",
})[props.position]);

const colourClass = computed(() => ({
  rainbow: "toast-rainbow text-white",
  slate: "bg-slate-900 text-white",
  blue: "bg-blue-600 text-white",
  green: "bg-emerald-600 text-white",
  amber: "bg-amber-400 text-amber-950",
  red: "bg-rose-600 text-white",
})[props.colour]);
</script>

<template>
  <div
    role="status"
    aria-live="polite"
    class="fixed z-50 flex w-max max-w-[calc(100vw-3rem)] items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium shadow-lg"
    :class="[positionClass, colourClass]"
  >
    <svg
      v-if="colour === 'green'"
      aria-hidden="true"
      class="size-5 shrink-0"
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path fill-rule="evenodd" d="M16.704 5.29a1 1 0 0 1 .006 1.414l-7.2 7.25a1 1 0 0 1-1.42 0l-3.8-3.825a1 1 0 1 1 1.42-1.408l3.09 3.11 6.49-6.535a1 1 0 0 1 1.414-.006Z" clip-rule="evenodd" />
    </svg>
    <span>{{ message }}</span>
    <button type="button" aria-label="Dismiss notification" class="rounded px-1 text-lg leading-none opacity-70 hover:bg-white/15 hover:opacity-100" @click="$emit('close')">&times;</button>
  </div>
</template>
