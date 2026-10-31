// @vitest-environment node
import { createServer as createHttpServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createServer, type ViteDevServer } from "vite";
import { server as msw } from "../src/mocks/node";

// The dev server must forward /v1 to the API (design: Local development). A stub stands
// in for the API on an ephemeral port; the real API check is the @real e2e test.

let api: Server;
let vite: ViteDevServer;
let seen: string[] = [];

beforeAll(async () => {
  msw.close(); // real sockets here: the shared setup's MSW interceptor must not answer
  api = createHttpServer((request, response) => {
    seen.push(request.url ?? "");
    response.setHeader("Content-Type", "application/json");
    response.end(JSON.stringify({ stub: true, path: request.url }));
  });
  await new Promise<void>((resolve) => api.listen(0, "127.0.0.1", resolve));
  process.env.OPENTRANSIT_API_ORIGIN = `http://127.0.0.1:${(api.address() as AddressInfo).port}`;
  vite = await createServer({
    configFile: fileURLToPath(new URL("../vite.config.ts", import.meta.url)),
    server: { port: 0, strictPort: false },
    logLevel: "silent",
  });
  await vite.listen();
});

afterAll(async () => {
  await vite?.close();
  await new Promise((resolve) => api?.close(resolve));
  delete process.env.OPENTRANSIT_API_ORIGIN;
});

describe("vite dev proxy", () => {
  it("forwards /v1 requests with their query to the API origin", async () => {
    seen = [];
    const base = vite.resolvedUrls!.local[0]!;
    const response = await fetch(new URL("/v1/status?probe=1", base));
    expect(await response.json()).toEqual({ stub: true, path: "/v1/status?probe=1" });
    expect(seen).toEqual(["/v1/status?probe=1"]);
  });

  it("serves the app itself, not the API, at /", async () => {
    seen = [];
    const response = await fetch(vite.resolvedUrls!.local[0]!);
    expect(await response.text()).toContain('<div id="root">');
    expect(seen).toEqual([]);
  });
});
