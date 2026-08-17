<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { useTasksStore } from "../stores/tasks";
import TaskItem from "../components/TaskItem.vue";
import AppButton from "../components/AppButton.vue";
import ToastNotification from "../components/ToastNotification.vue";

const tasks = useTasksStore();
const draft = ref("");
const toastMessage = ref("");
const toastId = ref(0);
let toastTimer: ReturnType<typeof setTimeout> | undefined;

function dismissToast() {
  clearTimeout(toastTimer);
  toastMessage.value = "";
}

function submit() {
  if (!draft.value.trim()) return;

  tasks.add(draft.value);
  draft.value = "";
  toastMessage.value = "Task added successfully!";
  toastId.value += 1;

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastMessage.value = "";
  }, 3000);
}

onBeforeUnmount(() => clearTimeout(toastTimer));
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

    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="translate-y-2 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-2 opacity-0"
    >
      <ToastNotification
        v-if="toastMessage"
        :key="toastId"
        :message="toastMessage"
        position="bottom-right"
        colour="green"
        @close="dismissToast"
      />
    </Transition>
  </section>
</template>
