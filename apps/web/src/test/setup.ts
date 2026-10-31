import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "../mocks/node";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
  // Node-environment tests (scripts/*.test.ts) have no web storage.
  globalThis.localStorage?.clear();
  globalThis.sessionStorage?.clear();
});
afterAll(() => server.close());
