import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 120000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:3000",
    viewport: { width: 1440, height: 980 },
    video: process.env.RECORD
      ? { mode: "on", size: { width: 1440, height: 980 } }
      : "retain-on-failure",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  outputDir: "../demo/recordings",
  reporter: [["list"], ["json", { outputFile: "../demo/e2e-results.json" }]],
  webServer: [
    {
      command:
        "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../api",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: process.env.E2E_REUSE_SERVER === "1",
      timeout: 60000,
    },
    {
      command: process.env.E2E_PRODUCTION
        ? "node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000"
        : "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: process.env.E2E_REUSE_SERVER === "1",
      timeout: 120000,
    },
  ],
});
