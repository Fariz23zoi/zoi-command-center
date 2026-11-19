import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Mode development: Vite (5173) meneruskan /api dan /ws ke backend (8000).
// Mode local: hasil build (dist/) disajikan langsung oleh backend — Vite tidak dipakai.
const backend = process.env.ZOI_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: backend },
      "/blueprint-studio": { target: backend },
      "/artefak-raw": { target: backend },
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 600 },
});
