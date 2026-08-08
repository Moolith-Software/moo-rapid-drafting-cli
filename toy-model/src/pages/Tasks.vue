<script setup lang="ts">
import { ref } from "vue";
import { useTasksStore } from "../stores/tasks";
import TaskItem from "../components/TaskItem.vue";
import AppButton from "../components/AppButton.vue";

const tasks = useTasksStore();
const draft = ref("");

function submit() {
  tasks.add(draft.value);
  draft.value = "";
}
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold text-slate-900">Tasks</h1>

    <form class="flex gap-2" @submit.prevent="submit">
      <input
        v-model="draft"
        placeholder="Add a task…"
        class="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-slate-900"
      />
      <AppButton type="submit">Add</AppButton>
    </form>

    <ul class="rounded-lg border border-slate-200 px-4">
      <TaskItem
        v-for="task in tasks.tasks"
        :key="task.id"
        :task="task"
        @toggle="tasks.toggle"
        @remove="tasks.remove"
      />
    </ul>
  </section>
</template>
