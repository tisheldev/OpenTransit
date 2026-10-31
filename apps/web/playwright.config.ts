import { defineConfig, devices } from "@playwright/test";

// Mocked suite: the dev server in `fixtures` mode answers /v1 with MSW, so no API or
// Docker is needed. `@real` tests target a running API and skip unless /readyz is 200.
const port = 5174;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${port}`,
    trace: "retain-on-failure",
    locale: "he-IL",
    timezoneId: "Asia/Jerusalem",
  },
  projects: [
    { name: "mobile-chromium", use: { ...devices["Pixel 7"], viewport: { width: 360, height: 640 } } },
  ],
  webServer: {
    command: `npx vite --mode fixtures --port ${port} --strictPort`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
