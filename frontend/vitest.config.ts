import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["apps/**/src/**/*.test.{ts,tsx}", "packages/**/src/**/*.test.{ts,tsx}"],
    setupFiles: ["apps/web/src/test/setup.ts"],
    css: false,
  },
});
