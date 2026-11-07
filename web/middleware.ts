// Signed-out visitors reach only the public pages (REQ-P08-S01-003). Every other route needs a session
// whose access token has not expired. Mock mode serves constructed data only, so it needs no session.

import { NextResponse, type NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

const PUBLIC = ["/", "/model", "/privacy", "/sign-in", "/unavailable"];

function isPublic(path: string) {
  return PUBLIC.includes(path) || path.startsWith("/api/auth/");
}

export async function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const headers = new Headers(request.headers);
  headers.set("x-dfu-path", `${path}${request.nextUrl.search}`);
  const next = () => NextResponse.next({ request: { headers } });

  if (process.env.NEXT_PUBLIC_DFU_MOCK === "1" || isPublic(path)) return next();

  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
  const expiresAt = typeof token?.expiresAt === "number" ? token.expiresAt : undefined;
  const live = token?.accessToken && (!expiresAt || expiresAt * 1000 > Date.now());
  if (live) return next();

  if (path.startsWith("/api/")) {
    return NextResponse.json({ error: { category: "UNAUTHENTICATED", failure_class: "CLIENT", code: "TOKEN_MISSING", message: "Sign in again" } }, { status: 401 });
  }
  const signIn = new URL("/sign-in", request.url);
  signIn.searchParams.set("callbackUrl", `${path}${request.nextUrl.search}`);
  return NextResponse.redirect(signIn);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\.(?:png|svg|jpg|jpeg|webp|ico|txt|woff2?)$).*)"],
};
