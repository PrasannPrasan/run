import type { LookupResult, ProviderStrategy, TokenResponse } from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL || "";
const isLoopbackBase = /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?/i.test(configuredBase);
const isLoopbackPage =
  typeof window !== "undefined" && /^(127\.0\.0\.1|localhost)$/.test(window.location.hostname);
const BASE = isLoopbackBase && !isLoopbackPage ? "" : configuredBase;

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(status: number, body: string) {
    super(extractErrorMessage(body));
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function extractErrorMessage(body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    return body || "Request failed";
  }
  return body || "Request failed";
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export function isAuthError(error: unknown): boolean {
  if (error instanceof ApiError) return error.status === 401;
  return error instanceof Error && /invalid token|user not found|not authenticated/i.test(error.message);
}

export async function register(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return readJson<TokenResponse>(res);
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  return readJson<TokenResponse>(res);
}

export async function enrich(linkedinUrl: string, token: string): Promise<{ lookupId: number; status: string }> {
  const res = await fetch(`${BASE}/api/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ linkedinUrl }),
  });
  return readJson<{ lookupId: number; status: string }>(res);
}

export async function getLookup(lookupId: number, token: string): Promise<LookupResult> {
  const res = await fetch(`${BASE}/api/enrich/lookups/${lookupId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson<LookupResult>(res);
}

export async function listLookups(token: string): Promise<{ items: LookupResult[] }> {
  const res = await fetch(`${BASE}/api/enrich/lookups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson<{ items: LookupResult[] }>(res);
}

export async function getStrategy(token: string): Promise<ProviderStrategy> {
  const res = await fetch(`${BASE}/api/enrich/strategy`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson<ProviderStrategy>(res);
}
