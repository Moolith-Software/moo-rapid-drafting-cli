import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // Honour PORT so a supervising harness can pin the dev server where it expects it.
  server: { port: Number(process.env.PORT) || 5173 },
});
