// Calls /api/v2 from the browser through the same-origin proxy route, which adds the bearer token.
// Constructed data has no service behind it, so callers check isMock before sending anything.

import { ApiError } from "@/lib/errors";

export async function send<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const response = await fetch(path.startsWith("/api/") ? path : `/api/v2${path}`, {
    ...rest,
    headers: json === undefined ? headers : { "Content-Type": "application/json", ...headers },
    body: json === undefined ? rest.body : JSON.stringify(json),
    cache: "no-store",
  });
  const body = await response.json().catch(() => undefined);
  if (!response.ok) throw ApiError.from(response.status, body, response.headers.get("Retry-After"));
  return body as T;
}

export async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

// The user-facing sentence for a failed call, without blaming the photo for a system fault.
export function problemText(error: unknown, messageFor: (category: string) => { title: string; body: string }): string {
  const copy = messageFor(error instanceof ApiError ? error.category : "INFRASTRUCTURE_FAILURE");
  return `${copy.title}. ${copy.body}`;
}
