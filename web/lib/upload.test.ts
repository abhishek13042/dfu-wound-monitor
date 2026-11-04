import { describe, expect, it } from "vitest";

import { problemWith, UPLOAD_LIMIT } from "@/lib/upload";

describe("upload checks in the browser", () => {
  it("accepts each supported type", () => {
    for (const [name, type] of [
      ["a.png", "image/png"],
      ["a.JPG", "image/jpeg"],
      ["a.jpeg", "image/jpeg"],
      ["a.bmp", "image/bmp"],
      ["a.tif", "image/tiff"],
      ["a.webp", "image/webp"],
    ]) {
      expect(problemWith({ name, type, size: 1024 })).toBeNull();
    }
  });

  it("rejects other types and a type that does not match the extension", () => {
    expect(problemWith({ name: "a.gif", type: "image/gif", size: 1024 })).toMatch(/not a PNG/);
    expect(problemWith({ name: "a.png", type: "application/pdf", size: 1024 })).toMatch(/not a PNG/);
    expect(problemWith({ name: "notes", type: "", size: 1024 })).toMatch(/not a PNG/);
  });

  it("rejects an empty file and one over 25 MB", () => {
    expect(problemWith({ name: "a.png", type: "image/png", size: 0 })).toMatch(/empty/);
    expect(problemWith({ name: "a.png", type: "image/png", size: UPLOAD_LIMIT })).toBeNull();
    expect(problemWith({ name: "a.png", type: "image/png", size: UPLOAD_LIMIT + 1 })).toMatch(/25 MB/);
  });
});
