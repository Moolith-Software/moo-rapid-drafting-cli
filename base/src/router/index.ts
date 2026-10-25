import { createRouter, createWebHistory } from "vue-router";
import Home from "../pages/Home.vue";
import Tasks from "../pages/Tasks.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: Home },
    { path: "/tasks", name: "tasks", component: Tasks },
  ],
});
