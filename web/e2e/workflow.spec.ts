import { expect, test, type Page } from "@playwright/test";

// REQ-P08-S02-006: sign in, create a case, upload, read the result and delete, against a running deployment
// with the real /api/v2 service, a worker and an OIDC provider. Set DFU_E2E_BASE_URL to run it. The provider
// must sign the user in without a form (oauth2-mock-server does), or set DFU_E2E_STORAGE to a saved session.
test.skip(!process.env.DFU_E2E_BASE_URL, "DFU_E2E_BASE_URL is not set");
test.use({ storageState: process.env.DFU_E2E_STORAGE });

// A constructed photo drawn in the browser: a flat skin tone with a darker ellipse and a printed scale. No real image.
async function syntheticPhoto(page: Page): Promise<Buffer> {
  const data = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 768;
    const context = canvas.getContext("2d")!;
    context.fillStyle = "#c99a7e";
    context.fillRect(0, 0, 1024, 768);
    context.fillStyle = "#8a3b34";
    context.beginPath();
    context.ellipse(512, 384, 150, 100, 0.3, 0, Math.PI * 2);
    context.fill();
    return canvas.toDataURL("image/png").split(",")[1];
  });
  return Buffer.from(data, "base64");
}

test("one case from sign-in to deletion", async ({ page }) => {
  await page.goto("/cases");
  if (new URL(page.url()).pathname === "/sign-in") {
    await page.getByRole("button", { name: /continue with/i }).click();
    await page.waitForURL("**/cases");
  }

  const label = `E2E ${Date.now()}`;
  await page.goto("/cases/new");
  await page.getByLabel("Label").fill(label);
  await page.getByRole("button", { name: "Create case" }).click();
  // /cases/new matches the case pattern too, so wait until the address names the created case.
  await page.waitForURL((url) => /^\/cases\/[^/]+$/.test(url.pathname) && url.pathname !== "/cases/new");
  const caseUrl = page.url();
  const caseId = caseUrl.split("/").pop()!;

  await page.goto(`/analyse?case=${caseId}`);
  await page.getByRole("checkbox", { name: /research use/ }).check();
  await page.locator('input[type="file"]').setInputFiles({ name: "constructed.png", mimeType: "image/png", buffer: await syntheticPhoto(page) });
  await page.getByLabel("Captured on").fill("2026-01-15");
  await page.getByRole("button", { name: "Read this photo" }).click();
  await page.waitForURL(/\/analyses\/[^/]+$/, { timeout: 60_000 });

  // The page polls until the worker finishes. A constructed photo may be measured or refused; both are results.
  const heading = page.getByRole("heading", { level: 1 });
  await expect(heading).toHaveText(/Photo accepted, region measured|Photo refused, nothing measured/, { timeout: 240_000 });
  if ((await heading.textContent())?.includes("region measured")) await expect(page.getByText(/Model /).first()).toBeVisible();

  await page.goto(caseUrl);
  await page.getByRole("button", { name: "Delete case" }).click();
  // The dialog asks for the case identifier, so a stray click cannot delete the wrong case.
  await page.getByRole("dialog").getByRole("textbox").fill(caseId);
  await page.getByRole("dialog").getByRole("button", { name: "Delete case" }).click();
  await page.waitForURL("**/cases");
  await expect(page.getByText(label)).toHaveCount(0);
});
