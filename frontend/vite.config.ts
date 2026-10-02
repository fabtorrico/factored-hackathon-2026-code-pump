import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const backendOrigin = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // The backend mounts its own routes under `/api`, so the prefix is preserved. Rewriting it
      // away would send `/api/transactions` to `/transactions` and produce a 404 for every read.
      "/api": {
        target: backendOrigin,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: false,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});