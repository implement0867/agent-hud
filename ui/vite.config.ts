import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { tsconfigPaths: true },
  // The server serves the build from inside its package.
  build: {
    outDir: "../server/src/agent_hud/static",
    emptyOutDir: true,
    // Shiki's grammars, theme and WebAssembly go in one chunk, which the page loads with the first code block.
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "shiki",
              test: /@shikijs[\\/](langs|themes)[\\/]|wasm-inlined|shiki[\\/]dist[\\/](wasm|themes)[\\/.]/,
            },
          ],
        },
      },
    },
  },
  server: { proxy: { "/ws": { target: "ws://127.0.0.1:7676", ws: true } } },
});
