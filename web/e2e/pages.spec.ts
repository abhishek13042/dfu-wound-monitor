import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { NOTICE } from "../lib/copy";

// Every page, against constructed data, in each state the mock layer can show.
const PAGES = [
  "/",
  "/model",
  "/sign-in",
  "/unavailable",
  "/cases",
  "/cases?state=empty",
  "/cases/new",
  "/cases/c-0007",
  "/cases/c-0007/trend",
  "/cases/c-0015/trend",
  "/analyse",
  "/analyse?error=QUALITY_REJECTED",
  "/analyses/a1d093",
  "/analyses/a1d066",
  "/analyses/c3f0a1",
  "/analyses/c3f0c9",
  "/compare",
  "/compare?a=a1d04e&b=b2e011",
  "/account",
  "/nothing-here",
];

for (const width of [1280, 375]) {
  test.describe(`at ${width} px`, () => {
    test.use({ viewport: { width, height: 900 } });

    for (const path of PAGES) {
      test(path, async ({ page }) => {
        await page.goto(path);
        await page.evaluate(() => document.fonts.ready);

        // REQ-P08-S01-002: the notice comes from the shared layouts, so it is on every page.
        await expect(page.getByText(NOTICE, { exact: true }).first()).toBeVisible();

        // REQ-P08-S01-005: nothing scrolls sideways at phone width.
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow).toBeLessThanOrEqual(0);

        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
        expect(results.violations.map((item) => `${item.id}: ${item.nodes.map((node) => node.target.join(" ")).join(", ")}`)).toEqual([]);
      });
    }
  });
}

test("the trend page carries its notice and lists exclusions with reasons", async ({ page }) => {
  await page.goto("/cases/c-0007/trend");
  await expect(page.getByRole("note").filter({ hasText: "Image-derived technical trends, not a healing assessment." })).toBeVisible();
  const excluded = page.getByRole("region", { name: "Left out of this trend" });
  await expect(excluded.getByRole("listitem")).toHaveCount(1);
  await expect(excluded.getByRole("listitem")).toContainText("30 Sept 2026");
  await expect(excluded.getByRole("listitem")).not.toContainText("MEASUREMENT_MISSING");
});

test("a trend with one usable point says so instead of drawing a line", async ({ page }) => {
  await page.goto("/cases/c-0015/trend");
  await expect(page.getByText(/A trend needs at least two/)).toBeVisible();
});

test("a pair the service refuses is reported, not drawn", async ({ page }) => {
  await page.goto("/compare?a=a1d04e&b=b2e011");
  await expect(page.getByRole("heading", { name: "These two cannot be compared" })).toBeVisible();
});
