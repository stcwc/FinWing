/** Thin fetch wrapper. All requests send cookies (httpOnly session).
 *  On a 401 the session cookie has expired, so we transparently refresh it once
 *  (POST /auth/refresh mints a new short-lived session cookie from the
 *  refresh-token cookie) and replay the request. This keeps users signed in for
 *  the life of the refresh token instead of being bounced every hour. */

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

/** Dispatched on window when a request stays 401 after a refresh attempt — i.e.
 *  the session has fully expired. The auth provider listens and signs the user
 *  out so they land on /signin instead of an empty signed-in view. */
export const SESSION_EXPIRED_EVENT = "finwing:session-expired";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// A single in-flight refresh shared by all concurrent 401s, so a burst of
// requests triggers exactly one /auth/refresh.
let refreshing: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  retried = false
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  // Expired session → refresh once and replay (but never recurse on /auth/refresh).
  if (res.status === 401 && !retried && path !== "/auth/refresh") {
    if (await refreshSession()) {
      return request<T>(method, path, body, true);
    }
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    // A 401 that survived the refresh attempt means the session is truly gone.
    // Signal the app to clear auth state and route to sign-in, rather than
    // letting callers render an empty/broken signed-in view.
    if (res.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const detail = data?.detail ?? data;
    throw new ApiError(
      res.status,
      detail?.code ?? "ERROR",
      detail?.message ?? res.statusText
    );
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};

/** Static config served from CloudFront (not the API). */
export async function loadStatic<T>(file: string): Promise<T> {
  const res = await fetch(`/static/${file}`);
  if (!res.ok) throw new Error(`Failed to load ${file}`);
  return res.json();
}
