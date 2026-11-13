/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server on http://localhost:5173 - one of the two origins the API allows (CORS, Phase 9.3).
// Tests run in "jsdom" (a simulated browser inside Node): no server, no network.
export default defineConfig({
  plugins: [react()],
  server: { host: "localhost", port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
