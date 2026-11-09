// One user message per /api/v2 error category (REQ-P08-S01-004). A quality rejection is a property of the
// photo and is never presented as a fault of the service, and a system fault never blames the photo.

import type { ErrorCategory } from "@/lib/api/types";
import { errorCopy } from "@/lib/copy";

export const CATEGORIES = Object.keys(errorCopy) as ErrorCategory[];

export type ErrorKind = "photo" | "request" | "system";

export interface ErrorBody {
  error: { category: string; failure_class: string; code: string; message: string; details?: unknown };
  request_id?: string;
}

const STATUS_CATEGORY: Record<number, ErrorCategory> = {
  400: "INVALID_INPUT",
  401: "UNAUTHENTICATED",
  403: "UNAUTHENTICATED",
  404: "NOT_FOUND",
  409: "CONFLICT",
  413: "INVALID_INPUT",
  415: "INVALID_INPUT",
  422: "INVALID_INPUT",
  429: "BUSY",
  503: "INFRASTRUCTURE_FAILURE",
};

export function isCategory(value: unknown): value is ErrorCategory {
  return typeof value === "string" && value in errorCopy;
}

export function kindOf(category: ErrorCategory): ErrorKind {
  if (category === "QUALITY_REJECTED") return "photo";
  if (category === "INVALID_INPUT" || category === "UNAUTHENTICATED" || category === "NOT_FOUND" || category === "CONFLICT") return "request";
  return "system";
}

// Copy for a category, with a fallback for a category this build does not know yet.
export function messageFor(category: string) {
  if (isCategory(category)) return { category, kind: kindOf(category), ...errorCopy[category] };
  return { category: "INFRASTRUCTURE_FAILURE" as const, kind: "system" as const, ...errorCopy.INFRASTRUCTURE_FAILURE };
}

export const UNREACHABLE = {
  title: "The service cannot be reached",
  body: "The analysis service did not answer. Nothing is shown in its place, and your earlier records are unchanged.",
  action: "Try again",
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly category: ErrorCategory,
    readonly failureClass: string,
    readonly code: string,
    readonly requestId?: string,
    readonly retryAfter?: number,
  ) {
    super(`${status} ${category} ${code}`);
    this.name = "ApiError";
  }

  static from(status: number, body: Partial<ErrorBody> = {}, retryAfter?: string | null): ApiError {
    const category = isCategory(body.error?.category) ? body.error.category : (STATUS_CATEGORY[status] ?? (status >= 500 ? "INFRASTRUCTURE_FAILURE" : "INVALID_INPUT"));
    const seconds = retryAfter ? Number(retryAfter) : undefined;
    return new ApiError(
      status,
      category,
      body.error?.failure_class ?? (status >= 500 ? "SYSTEM" : "CLIENT"),
      body.error?.code ?? `HTTP_${status}`,
      body.request_id,
      Number.isFinite(seconds) ? seconds : undefined,
    );
  }
}
