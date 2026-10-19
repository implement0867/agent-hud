/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

// The build lands inside the Python package so the MCP server can serve it without Node.
export default defineConfig({
  plugins: [react(), tailwindcss(), tsconfigPaths()],
  build: {
    outDir: "../server/src/agent_hud/static",
    emptyOutDir: true,
    sourcemap: false,
    // One bundle served from localhost; markdown rendering is most of its size.
    chunkSizeWarningLimit: 700,
  },
  server: {
    // Run `uv run agent-hud --mode serve --demo --extra_origins '["http://localhost:5173"]'` alongside.
    proxy: { "/ws": { target: "ws://127.0.0.1:7676", ws: true } },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
