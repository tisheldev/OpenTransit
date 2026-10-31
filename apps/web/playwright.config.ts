import { defineConfig, devices } from "@playwright/test";

// Default (mocked) mode: the dev server in `fixtures` mode answers /v1 with MSW, so no API
// or Docker is needed. `@real` tests target a running API and skip unless /readyz is 200.
// OT_E2E_PORT lets parallel worktrees run their own dev servers without sharing one.
//
// Served mode: OT_E2E_BASE_URL (for example http://127.0.0.1:8590/app/) runs against a
// build the API already serves, with no dev server. That build has no MSW, so only the
// `@real` specs (e2e/real*.spec.ts) run; tests navigate with appPath() so both bases work.
const port = Number(process.env.OT_E2E_PORT ?? 5174);
const servedBaseUrl = process.env.OT_E2E_BASE_URL;
const baseURL = servedBaseUrl ? servedBaseUrl.replace(/\/?$/, "/") : `http://localhost:${port}`;

export default defineConfig({
  testDir: "./e2e",
  ...(servedBaseUrl ? { testMatch: /real.*\.spec\.ts$/ } : {}),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    locale: "he-IL",
    timezoneId: "Asia/Jerusalem",
  },
  projects: [
    { name: "mobile-chromium", use: { ...devices["Pixel 7"], viewport: { width: 360, height: 640 } } },
  ],
  ...(servedBaseUrl
    ? {}
    : {
        webServer: {
          command: `npx vite --mode fixtures --port ${port} --strictPort`,
          url: `http://localhost:${port}`,
          reuseExistingServer: !process.env.CI,
          timeout: 60_000,
        },
      }),
});
