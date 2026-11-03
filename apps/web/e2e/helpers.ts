import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

// Shared e2e helpers. Navigate with appPath() so the same tests run against the dev
// server (base "/") and the build served by the API (base "/app/").

/** `hash` like "#/settings"; resolved against the configured baseURL's directory. */
export function appPath(hash = ""): string {
  return `./${hash}`;
}

/** Fixture scenario read by the MSW handlers (src/mocks/handlers.ts scenario()). */
export async function useScenario(page: Page, scenario: string | null): Promise<void> {
  await page.addInitScript((value) => {
    if (value === null) localStorage.removeItem("ot-fixture-scenario");
    else localStorage.setItem("ot-fixture-scenario", value);
  }, scenario);
}

/** Fails on serious or critical axe violations (acceptance: no serious violations). */
export async function expectNoSeriousAxeViolations(page: Page, label: string): Promise<void> {
  // The map canvas is decorative here: every map fact is also present as text.
  const results = await new AxeBuilder({ page }).exclude(".maplibregl-canvas").analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(
    serious.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(" ")).join(", ")})`),
    `axe on ${label}`,
  ).toEqual([]);
}

/** Block every request that leaves localhost (map tiles in mocked runs). */
export async function blockExternal(page: Page): Promise<void> {
  await page.route(/^https?:\/\/(?!localhost|127\.0\.0\.1)/, (route) => route.abort());
}
