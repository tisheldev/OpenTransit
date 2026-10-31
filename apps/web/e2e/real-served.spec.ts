import { expect, test, type Page } from "@playwright/test";
import { appPath, expectNoSeriousAxeViolations } from "./helpers";

// @real, served build only (OT_E2E_BASE_URL, e.g. http://127.0.0.1:8590/app/): a tester's
// whole flow through the UI on a 360 × 640 phone in Hebrew, with axe on every screen.
// "My location" is granted as Dizengoff Center (a corpus stop, not a personal position).

const apiOrigin = process.env.OPENTRANSIT_API_ORIGIN ?? "http://localhost:8000";
const served = !!process.env.OT_E2E_BASE_URL;

test.use({
  geolocation: { latitude: 32.0753, longitude: 34.7749, accuracy: 20 },
  permissions: ["geolocation"],
});

async function expectPhoneLayout(page: Page, label: string) {
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "he");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, `${label}: no horizontal scroll at 360 px`).toBeLessThanOrEqual(0);
  await expectNoSeriousAxeViolations(page, label);
}

test.describe("@real served", () => {
  test.beforeAll(async ({ request }) => {
    test.skip(!served, "needs the build served by the API (OT_E2E_BASE_URL)");
    const ready = await request.get(`${apiOrigin}/readyz`, { timeout: 5_000 }).catch(() => null);
    test.skip(ready?.status() !== 200, `API at ${apiOrigin} is not ready`);
  });

  test("Home → Search → Compare → Navigate → Settings in Hebrew at 360 × 640, axe clean", async ({ page }) => {
    test.setTimeout(90_000);
    expect(page.viewportSize()).toEqual({ width: 360, height: 640 });

    await page.goto(appPath("#/"));
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByTestId("map-attribution")).toBeVisible();
    await expectPhoneLayout(page, "Home");

    await page.getByRole("button", { name: /לאן\?/ }).first().click();
    await expect(page).toHaveURL(/#\/search\/to$/);
    const places = page.waitForResponse((r) => new URL(r.url()).pathname === "/v1/places" && r.status() === 200);
    await page.getByRole("searchbox").or(page.getByRole("textbox")).first().fill("טכניון");
    await places;
    const result = page.locator("main").getByRole("button", { name: /טכניון/ }).first();
    await expect(result).toBeVisible();
    await expectPhoneLayout(page, "Search results");

    const journeys = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith("/v1/journeys"));
    await result.click();
    await expect(page).toHaveURL(/#\/compare$/);
    const answer = await journeys;
    expect(answer.status()).toBe(200);
    const body = await answer.json();
    expect(body.meta.mode).toBe("real");
    test.info().annotations.push({ type: "outcome", description: `${body.data.outcome}, ${body.data.journeys.length} journeys` });
    if (body.data.outcome === "routes_found") {
      await expect(page.getByRole("list", { name: "אפשרויות נסיעה" }).getByRole("button").first()).toBeVisible();
    }
    await expectPhoneLayout(page, "Compare");

    if (body.data.outcome === "routes_found") {
      await page.getByRole("button", { name: "התחלת ניווט" }).click();
      await expect(page).toHaveURL(/#\/navigate$/);
      await expect(page.getByRole("button", { name: /השלב הבא|סיום/ }).first()).toBeVisible();
      await expectPhoneLayout(page, "Navigate");
      await page.getByRole("button", { name: "סיום הנסיעה" }).click();
      await expect(page).toHaveURL(/#\/$/);
    }

    await page.goto(appPath("#/settings"));
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectPhoneLayout(page, "Settings");
  });
});
