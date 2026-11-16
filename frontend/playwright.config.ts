import { defineConfig, devices } from "@playwright/test";

// E2E dijalankan di workspace pengembangan (bukan di laptop/local server).
// Dua skenario: development (Vite + backend mock) dan local (backend menyajikan dist di satu port, tanpa Vite).
const stamp = Date.now();
const python = process.env.E2E_PYTHON ?? "../backend/.venv/bin/python";
const chrome = process.env.E2E_CHROME; // browser sistem bila unduhan browser Playwright tidak tersedia
const LOCAL_PORT = 8080; // port alternatif — port 80 di local server Windows diuji saat migrasi
const FAKE_OLLAMA_PORT = 11500; // Ollama TIRUAN (backend/tests/fake_ollama.py) — tidak ada model sungguhan

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  workers: 1,
  reporter: [["list"]],
  use: {
    launchOptions: {
      ...(chrome ? { executablePath: chrome } : {}),
      // WebGL perangkat lunak (SwiftShader) agar avatar 3D bisa diuji di mesin tanpa GPU; audio boleh diputar otomatis.
      args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--autoplay-policy=no-user-gesture-required"],
    },
    trace: "off",
  },
  projects: [
    { name: "development-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, baseURL: "http://127.0.0.1:5173" } },
    { name: "development-mobile", use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 }, hasTouch: true, baseURL: "http://127.0.0.1:5173" } },
    { name: "local-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, baseURL: `http://127.0.0.1:${LOCAL_PORT}` } },
    { name: "local-tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 }, baseURL: `http://127.0.0.1:${LOCAL_PORT}` } },
  ],
  webServer: [
    {
      command: `${python} -m app`,
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      env: { ZOI_MODE: "development", ZOI_PORT: "8000", ZOI_DATA_DIR: `/tmp/zoi-e2e-dev-${stamp}`, ZOI_MOCK_LATENCY_MS: "40",
        ZOI_ENV_FILE: "/nonexistent" },
    },
    {
      command: "npm --workspace @zoi/web run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
    },
    {
      command: `${python} -m tests.fake_ollama --port ${FAKE_OLLAMA_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${FAKE_OLLAMA_PORT}/api/version`,
      reuseExistingServer: false,
    },
    {
      command: `${python} -m app`,
      cwd: "../backend",
      url: `http://127.0.0.1:${LOCAL_PORT}/api/health`,
      reuseExistingServer: false,
      env: { ZOI_MODE: "local", ZOI_PORT: String(LOCAL_PORT), ZOI_DATA_DIR: `/tmp/zoi-e2e-local-${stamp}`,
        ZOI_OLLAMA_URL: `http://127.0.0.1:${FAKE_OLLAMA_PORT}`, ZOI_OLLAMA_MODEL: "qwen3:4b",
        ZOI_ENV_FILE: "/nonexistent" },
    },
  ],
});
