import { cookies } from "next/headers";

import { API_BASE_URL } from "./api-base";

type RequestOptions = RequestInit & {
  json?: unknown;
};

export { API_BASE_URL } from "./api-base";

export async function serverFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((item) => `${item.name}=${item.value}`)
    .join("; ");

  const headers = new Headers(options.headers || {});
  if (cookieHeader) {
    headers.set("cookie", cookieHeader);
  }
  if (options.json !== undefined) {
    headers.set("content-type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
    body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed for ${path}`);
  }

  return response.json() as Promise<T>;
}
