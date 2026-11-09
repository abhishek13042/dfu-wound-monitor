import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { middleware } from "./middleware";

// REQ-P08-S01-003: without a session, only the public pages answer.
describe("signed-out access", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_DFU_MOCK", "0");
    vi.stubEnv("NEXTAUTH_SECRET", "test-only-secret");
  });

  const visit = (path: string) => middleware(new NextRequest(new URL(path, "http://localhost:3000")));

  it.each(["/", "/model", "/privacy", "/sign-in", "/unavailable", "/api/auth/session"])("lets %s through", async (path) => {
    const response = await visit(path);
    expect(response.headers.get("location")).toBeNull();
    expect(response.status).toBe(200);
  });

  it.each(["/cases", "/cases/c-1/trend", "/analyse?case=c-1", "/analyses/a-1", "/compare", "/account"])("sends %s to sign-in", async (path) => {
    const response = await visit(path);
    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("location")!);
    expect(location.pathname).toBe("/sign-in");
    expect(location.searchParams.get("callbackUrl")).toBe(path);
  });

  it("answers the API proxy with 401 rather than a redirect", async () => {
    const response = await visit("/api/v2/cases");
    expect(response.status).toBe(401);
    expect((await response.json()).error.category).toBe("UNAUTHENTICATED");
  });
});
