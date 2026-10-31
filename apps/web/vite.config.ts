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

/**
 * The headers the API's /app/ mount sends (S8 contract). `vite preview` sends them too, so
 * a build can be checked under the real CSP (MapLibre's worker, tiles, styles) locally.
 */
export const clientSecurityHeaders: Record<string, string> = {
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data: blob: https://tiles.openfreemap.org",
    "font-src 'self'",
    "connect-src 'self' https://tiles.openfreemap.org",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
  ].join("; "),
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Content-Type-Options": "nosniff",
};

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
  preview: {
    headers: clientSecurityHeaders,
  },
  // MapLibre is imported only by the lazy map chunk; pre-bundle it so the dev server does
  // not discover it late and reload the page.
  optimizeDeps: { include: ["maplibre-gl"] },
  build: {
    target: "es2022",
    sourcemap: true,
    // The lazy MapLibre chunk is ~1 MB raw (~270 kB gzipped) by itself; the initial
    // bundle has its own 150 kB-gzipped budget (design: Stack and hosting).
    chunkSizeWarningLimit: 1100,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "scripts/**/*.test.ts"],
    restoreMocks: true,
  },
});
