import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { NOTICE } from "../lib/copy";

// Every page, against constructed data, in each state the mock layer can show.
const PAGES = [
  "/",
  "/model",
  "/privacy",
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
  "/analyses/a1d079",
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

test("the heatmap toggles in place of the outline and the uncertainty is worded as such", async ({ page }) => {
  await page.goto("/analyses/a1d04e");
  const heatmap = page.getByRole("button", { name: "Heatmap" });
  await expect(page.getByRole("button", { name: "Outline", exact: true })).toHaveAttribute("aria-pressed", "true");
  await heatmap.click();
  await expect(heatmap).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Model score per pixel")).toBeVisible();
  // REQ-P09-S02-004
  const panel = page.getByRole("region", { name: "Model uncertainty" });
  await expect(panel).toContainText("It is not the chance that the outline is correct.");
  await expect(panel).not.toContainText(/confiden|\d+\s*%/i);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((item) => item.id)).toEqual([]);
});

// REQ-P09-S03-001: draw, undo and redo, keep a draft across a reload, and save.
test("the outline editor draws, undoes, keeps a draft and saves", async ({ page }) => {
  await page.goto("/analyses/a1d079");
  await page.getByRole("button", { name: "Correct it again" }).click();
  const canvas = page.getByRole("img", { name: /Outline being corrected/ });
  const covered = () =>
    canvas.evaluate((element: HTMLCanvasElement) => {
      const data = element.getContext("2d")!.getImageData(0, 0, element.width, element.height).data;
      let count = 0;
      for (let i = 3; i < data.length; i += 4) if (data[i] >= 128) count += 1;
      return count;
    });
  await expect.poll(covered).toBeGreaterThan(0);
  const model = await covered();
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + 10, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + 120, box.y + 40, { steps: 6 });
  await page.mouse.up();
  const drawn = await covered();
  expect(drawn).toBeGreaterThan(model);

  await page.getByRole("button", { name: "Undo" }).click();
  expect(await covered()).toBe(model);
  await page.getByRole("button", { name: "Redo" }).click();
  expect(await covered()).toBe(drawn);

  await page.reload();
  await page.getByRole("button", { name: "Correct it again" }).click();
  await page.getByRole("button", { name: "Restore draft" }).click();
  await expect.poll(covered).toBe(drawn);

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((item) => item.id)).toEqual([]);

  await page.getByRole("button", { name: "Save corrected outline" }).click();
  await expect(page.getByText(`The outline covers ${drawn.toLocaleString("en-GB")} px²`)).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("dfu-mask-draft:a1d079"))).toBeNull();
});

test("a trend value from a corrected outline is marked", async ({ page }) => {
  await page.goto("/cases/c-0007/trend");
  const row = page.getByRole("row").filter({ hasText: "Corrected outline" });
  await expect(row).toHaveCount(1);
  await expect(row).toContainText("14 Oct 2026");
});

test.describe("on a touch screen", () => {
  test.use({ viewport: { width: 375, height: 812 }, hasTouch: true, isMobile: true });

  // REQ-P09-S03-001: a finger drag draws, and the page does not scroll under it.
  test("a finger drag draws on the outline", async ({ page }) => {
    await page.goto("/analyses/a1d079");
    await page.getByRole("button", { name: "Correct it again" }).click();
    const canvas = page.getByRole("img", { name: /Outline being corrected/ });
    const covered = () =>
      canvas.evaluate((element: HTMLCanvasElement) => {
        const data = element.getContext("2d")!.getImageData(0, 0, element.width, element.height).data;
        let count = 0;
        for (let i = 3; i < data.length; i += 4) if (data[i] >= 128) count += 1;
        return count;
      });
    await expect.poll(covered).toBeGreaterThan(0);
    const before = await covered();
    await canvas.scrollIntoViewIfNeeded();
    const box = (await canvas.boundingBox())!;
    const scrolled = await page.evaluate(() => window.scrollY);
    const cdp = await page.context().newCDPSession(page);
    const at = (x: number, y: number) => [{ x: box.x + x, y: box.y + y }];
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(8, 8) });
    for (let step = 1; step <= 8; step += 1) await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at(8 + step * 12, 8 + step * 6) });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect.poll(covered).toBeGreaterThan(before);
    expect(await page.evaluate(() => window.scrollY)).toBe(scrolled);
  });
});
