import { defineStore } from "pinia";
import { ref, computed } from "vue";

export interface Task {
  id: number;
  title: string;
  done: boolean;
}

export const useTasksStore = defineStore("tasks", () => {
  const tasks = ref<Task[]>([
    { id: 1, title: "Sketch the onboarding flow", done: true },
    { id: 2, title: "Wire up the settings page", done: false },
    { id: 3, title: "Write the release notes", done: false },
  ]);

  let nextId = 4;

  const remaining = computed(() => tasks.value.filter((t) => !t.done).length);

  function add(title: string) {
    const trimmed = title.trim();
    if (!trimmed) return;
    tasks.value.push({ id: nextId++, title: trimmed, done: false });
  }

  function toggle(id: number) {
    const task = tasks.value.find((t) => t.id === id);
    if (task) task.done = !task.done;
  }

  function remove(id: number) {
    tasks.value = tasks.value.filter((t) => t.id !== id);
  }

  return { tasks, remaining, add, toggle, remove };
});
