import type { LookupResult, ProviderStrategy, TokenResponse } from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL || "";

export async function register(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function enrich(linkedinUrl: string, token: string): Promise<{ lookupId: number; status: string }> {
  const res = await fetch(`${BASE}/api/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ linkedinUrl }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getLookup(lookupId: number, token: string): Promise<LookupResult> {
  const res = await fetch(`${BASE}/api/enrich/lookups/${lookupId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listLookups(token: string): Promise<{ items: LookupResult[] }> {
  const res = await fetch(`${BASE}/api/enrich/lookups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getStrategy(token: string): Promise<ProviderStrategy> {
  const res = await fetch(`${BASE}/api/enrich/strategy`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
