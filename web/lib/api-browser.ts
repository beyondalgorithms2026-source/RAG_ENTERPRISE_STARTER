import { browserApiUrl } from "./api-base";

type RequestOptions = RequestInit & {
  json?: unknown;
};

export { browserApiUrl } from "./api-base";

export async function browserFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (options.json !== undefined) {
    headers.set("content-type", "application/json");
  }

  const response = await fetch(browserApiUrl(path), {
    ...options,
    headers,
    credentials: "include",
    body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
  });

  if (!response.ok) {
    const text = await response.text();
    let message = text || `Request failed for ${path}`;
    try {
      const parsed = text ? JSON.parse(text) as { detail?: unknown; message?: unknown; error?: unknown } : {};
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      } else if (parsed.detail && typeof parsed.detail === "object") {
        const detail = parsed.detail as { message?: unknown; error?: unknown };
        if (typeof detail.message === "string" && detail.message.trim()) {
          message = detail.message;
        } else if (typeof detail.error === "string" && detail.error.trim()) {
          message = detail.error;
        }
      } else if (typeof parsed.message === "string" && parsed.message.trim()) {
        message = parsed.message;
      } else if (typeof parsed.error === "string" && parsed.error.trim()) {
        message = parsed.error;
      }
    } catch {
      // Keep the raw response body when it is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}
