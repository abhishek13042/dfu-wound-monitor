import { describe, expect, it } from "vitest";

import { errorCopy } from "@/lib/copy";
import { ApiError, CATEGORIES, kindOf, messageFor } from "@/lib/errors";

describe("error messages", () => {
  it("covers all nine categories with a title, explanation and action", () => {
    expect(CATEGORIES).toHaveLength(9);
    for (const category of CATEGORIES) {
      const copy = messageFor(category);
      expect(copy.title.length).toBeGreaterThan(0);
      expect(copy.body.length).toBeGreaterThan(0);
      expect(copy.action.length).toBeGreaterThan(0);
    }
  });

  it("gives every category a distinct title", () => {
    const titles = CATEGORIES.map((category) => errorCopy[category].title);
    expect(new Set(titles).size).toBe(titles.length);
  });

  it("keeps quality rejection apart from system failure", () => {
    expect(kindOf("QUALITY_REJECTED")).toBe("photo");
    for (const category of ["MODEL_FAILURE", "MODEL_NOT_READY", "INFRASTRUCTURE_FAILURE", "BUSY"] as const) {
      expect(kindOf(category)).toBe("system");
      expect(errorCopy[category].body.toLowerCase()).not.toContain("photo failed");
    }
    expect(errorCopy.QUALITY_REJECTED.body).toMatch(/failed one or more checks/);
  });

  it("falls back to a system message for an unknown category", () => {
    expect(messageFor("SOMETHING_NEW").kind).toBe("system");
  });

  it("reads the category from the body and falls back to the status", () => {
    const body = { error: { category: "BUSY", failure_class: "TRANSIENT", code: "QUEUE_FULL", message: "" }, request_id: "r1" };
    const fromBody = ApiError.from(429, body, "20");
    expect([fromBody.category, fromBody.code, fromBody.requestId, fromBody.retryAfter]).toEqual(["BUSY", "QUEUE_FULL", "r1", 20]);
    expect(ApiError.from(404).category).toBe("NOT_FOUND");
    expect(ApiError.from(502).category).toBe("INFRASTRUCTURE_FAILURE");
  });
});
