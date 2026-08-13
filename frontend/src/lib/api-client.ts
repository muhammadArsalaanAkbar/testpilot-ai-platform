/**
 * Typed HTTP client for the TestPilot API. Every call goes through here so
 * error-envelope parsing, auth header attachment, and 401→refresh retry are
 * handled in exactly one place (plan.md API Design; contracts/_conventions.md).
 */

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.error.code;
    this.details = body.error.details ?? {};
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

let accessToken: string | null = null;

/** Set by the auth layer (Phase 4) after login/signup/refresh. */
export function setAccessToken(token: string | null): void {
  accessToken = token;
}

type RefreshHandler = () => Promise<string | null>;
let refreshHandler: RefreshHandler | null = null;

/** Registered once by the auth layer; called on a 401 to attempt a silent
 * token refresh before retrying the original request exactly once. */
export function setRefreshHandler(handler: RefreshHandler | null): void {
  refreshHandler = handler;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** Skip the automatic 401→refresh retry (used by the refresh call itself). */
  skipAuthRetry?: boolean;
}

async function parseErrorBody(response: Response): Promise<ApiErrorBody> {
  try {
    const data = (await response.json()) as unknown;
    if (
      data &&
      typeof data === "object" &&
      "error" in data &&
      typeof (data as ApiErrorBody).error?.code === "string"
    ) {
      return data as ApiErrorBody;
    }
  } catch {
    // fall through to the generic envelope below
  }
  return {
    error: { code: "unknown_error", message: `Request failed with status ${response.status}` },
  };
}

async function rawRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    credentials: "include", // carries the httpOnly refresh cookie
    signal: options.signal,
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 401 && !options.skipAuthRetry && refreshHandler) {
    const newToken = await refreshHandler();
    if (newToken) {
      accessToken = newToken;
      return rawRequest<T>(path, { ...options, skipAuthRetry: true });
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string, signal?: AbortSignal) => rawRequest<T>(path, { method: "GET", signal }),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    rawRequest<T>(path, { method: "POST", body, signal }),
  patch: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    rawRequest<T>(path, { method: "PATCH", body, signal }),
  put: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    rawRequest<T>(path, { method: "PUT", body, signal }),
  delete: <T>(path: string, signal?: AbortSignal) =>
    rawRequest<T>(path, { method: "DELETE", signal }),
  /** For DELETE endpoints that require a confirmation body (e.g. `{confirm:
   * true}`, contracts/projects-api.md) — `delete()` has no body param since
   * most DELETEs don't need one. */
  deleteWithBody: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    rawRequest<T>(path, { method: "DELETE", body, signal }),
  /**
   * For the registered refresh handler's own call to POST /auth/refresh
   * ONLY. A 401 from the refresh endpoint itself must never trigger another
   * refresh attempt — rawRequest's normal 401 handling calls
   * `refreshHandler()`, and the refresh handler's own request going through
   * that same path would call itself recursively without ever terminating
   * (a real bug this shape exists specifically to prevent).
   */
  postSkipAuthRetry: <T>(path: string, body?: unknown) =>
    rawRequest<T>(path, { method: "POST", body, skipAuthRetry: true }),
  /** For multipart file uploads (e.g. issue attachments, contracts/issues-api.md)
   * — cannot go through `rawRequest`, which always JSON-stringifies the body
   * and sets `Content-Type: application/json`; a `FormData` body needs the
   * browser to set its own `Content-Type` with the multipart boundary. */
  postMultipart: <T>(path: string, formData: FormData) => rawMultipartRequest<T>(path, formData),
};

async function rawMultipartRequest<T>(path: string, formData: FormData, skipAuthRetry = false): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    body: formData,
  });

  if (response.status === 401 && !skipAuthRetry && refreshHandler) {
    const newToken = await refreshHandler();
    if (newToken) {
      accessToken = newToken;
      return rawMultipartRequest<T>(path, formData, true);
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as T;
}
