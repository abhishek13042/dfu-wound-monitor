// Server-side client for /api/v2, typed from the generated schema. Every request carries the signed-in
// user's access token. An unreachable service, an expired session and a service outage each send the
// visitor to a page that says so, and no constructed data is ever shown in their place (REQ-P08-S01-003, -004).

import createClient from "openapi-fetch";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { getToken } from "next-auth/jwt";

import { ApiError, type ErrorBody } from "@/lib/errors";
import type { paths } from "./schema";

export const apiUrl = () => (process.env.DFU_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export async function accessToken(): Promise<string | undefined> {
  const jar = await cookies();
  const token = await getToken({
    req: { headers: Object.fromEntries((await headers()).entries()), cookies: Object.fromEntries(jar.getAll().map((c) => [c.name, c.value])) } as never,
    secret: process.env.NEXTAUTH_SECRET,
  });
  return typeof token?.accessToken === "string" ? token.accessToken : undefined;
}

async function currentPath() {
  return (await headers()).get("x-dfu-path") ?? "/cases";
}

export async function api() {
  const token = await accessToken();
  return createClient<paths>({
    baseUrl: apiUrl(),
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

type Result<T> = { data?: T; error?: unknown; response: Response };

// Unwraps a call. NOT_FOUND becomes undefined so pages can call notFound().
export async function call<T>(request: Promise<Result<T>>): Promise<T | undefined> {
  let result: Result<T>;
  try {
    result = await request;
  } catch {
    redirect("/unavailable");
  }
  if (result.data !== undefined && result.response.ok) return result.data;
  const body = (result.error ?? {}) as Partial<ErrorBody>;
  const error = ApiError.from(result.response.status, body, result.response.headers.get("Retry-After"));
  if (error.category === "NOT_FOUND") return undefined;
  if (error.category === "UNAUTHENTICATED") redirect(`/sign-in?callbackUrl=${encodeURIComponent(await currentPath())}`);
  if (error.category === "MODEL_NOT_READY" || error.category === "INFRASTRUCTURE_FAILURE")
    redirect(`/unavailable?category=${error.category}&code=${encodeURIComponent(error.code)}`);
  throw error;
}
