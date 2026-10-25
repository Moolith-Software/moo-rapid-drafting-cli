<script setup lang="ts">
import type { Task } from "../stores/tasks";
import AppButton from "./AppButton.vue";

defineProps<{ task: Task }>();
defineEmits<{ toggle: [id: number]; remove: [id: number] }>();
</script>

<template>
  <li class="flex items-center gap-3 border-b border-slate-100 py-2 last:border-0">
    <input
      type="checkbox"
      class="size-4 accent-slate-900"
      :checked="task.done"
      @change="$emit('toggle', task.id)"
    />
    <span class="flex-1 text-sm" :class="task.done ? 'text-slate-400 line-through' : 'text-slate-800'">
      {{ task.title }}
    </span>
    <AppButton variant="ghost" @click="$emit('remove', task.id)">Remove</AppButton>
  </li>
</template>
