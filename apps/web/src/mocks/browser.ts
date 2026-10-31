import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/** Start fixture mode: every /v1 request is answered from fixtures in the browser. */
export async function startFixtureMode(): Promise<void> {
  await setupWorker(...handlers).start({ onUnhandledRequest: "bypass", quiet: true });
}
