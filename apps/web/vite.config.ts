/// <reference types="vitest/config" />
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Every unit test runs under a UTC host so time code cannot lean on the machine's
// zone. `npm run test:tz` reruns the suite under other zones through OT_TEST_TZ.
process.env.TZ = process.env.OT_TEST_TZ ?? "UTC";

/** Where the dev server forwards `/v1`; the API's default local port. */
export const apiOrigin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";

/**
 * Serve MSW's worker script only in the dev server's `fixtures` mode. It is never
 * copied into a build: the preview has no service worker.
 */
function fixtureWorker(): Plugin {
  const require = createRequire(import.meta.url);
  return {
    name: "opentransit-fixture-worker",
    apply: "serve",
    configureServer(server) {
      if (server.config.mode !== "fixtures") return;
      const script = readFileSync(require.resolve("msw/mockServiceWorker.js"));
      server.middlewares.use("/mockServiceWorker.js", (_req, res) => {
        res.setHeader("Content-Type", "text/javascript");
        res.end(script);
      });
    },
  };
}

export default defineConfig({
  // Built files are served by the API at /app/ (design: Stack and hosting).
  base: process.env.NODE_ENV === "production" ? "/app/" : "/",
  plugins: [react(), fixtureWorker()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/v1": { target: apiOrigin, changeOrigin: false },
      "/readyz": { target: apiOrigin, changeOrigin: false },
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "scripts/**/*.test.ts"],
    restoreMocks: true,
  },
});
