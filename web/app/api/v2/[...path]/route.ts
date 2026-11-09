// Same-origin relay to /api/v2 for the browser: job polling, uploads and stored photos. The service sends
// no CORS headers, and the access token lives only on the server, so the browser never calls it directly.

import { NextResponse, type NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

import { apiUrl } from "@/lib/api/http";
import { isMock } from "@/lib/api/mode";

const PASSED = ["content-type", "retry-after", "content-length", "content-disposition", "cache-control", "etag"];

async function relay(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  if (isMock) return NextResponse.json({ error: { category: "NOT_FOUND", code: "MOCK_MODE", message: "No service in mock mode" } }, { status: 404 });
  const { path } = await params;
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
  const headers = new Headers();
  for (const name of ["content-type", "accept", "if-none-match"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (typeof token?.accessToken === "string") headers.set("authorization", `Bearer ${token.accessToken}`);
  const target = `${apiUrl()}/api/v2/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // Required by Node fetch when streaming a request body.
      ...(hasBody ? { duplex: "half" } : {}),
      cache: "no-store",
      redirect: "manual",
    } as RequestInit);
  } catch {
    return NextResponse.json({ error: { category: "UNREACHABLE", failure_class: "SYSTEM", code: "SERVICE_UNREACHABLE", message: "" } }, { status: 502 });
  }
  const out = new Headers();
  for (const name of PASSED) {
    const value = response.headers.get(name);
    if (value) out.set(name, value);
  }
  return new NextResponse(response.body, { status: response.status, headers: out });
}

export { relay as GET, relay as POST, relay as PUT, relay as DELETE };
