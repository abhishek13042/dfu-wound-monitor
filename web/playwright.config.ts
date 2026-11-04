import { defineConfig, devices } from "@playwright/test";

// Two suites. "pages" builds the app against constructed data and checks every page (REQ-P08-S01-002, -005).
// "workflow" drives a running deployment with the real API, worker and an OIDC provider (REQ-P08-S02-006);
// it runs only when DFU_E2E_BASE_URL names that deployment.
const PORT = 3100;
const live = process.env.DFU_E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: { trace: "retain-on-failure" },
  projects: [
    {
      name: "pages",
      testMatch: "pages.spec.ts",
      use: { ...devices["Desktop Chrome"], baseURL: `http://localhost:${PORT}` },
    },
    {
      name: "workflow",
      testMatch: "workflow.spec.ts",
      timeout: 300_000,
      use: { ...devices["Desktop Chrome"], baseURL: live },
    },
  ],
  // Only the pages suite needs the mock build. Building it while a live run is pointed elsewhere would
  // overwrite .next under the deployment being tested.
  webServer: live
    ? undefined
    : {
        command: `npm run build && npm run start -- -p ${PORT}`,
        url: `http://localhost:${PORT}`,
        timeout: 300_000,
        reuseExistingServer: !process.env.CI,
        env: { NEXT_PUBLIC_DFU_MOCK: "1" },
      },
});
