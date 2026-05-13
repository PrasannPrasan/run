import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { enrich, getLookup, getStrategy, listLookups, login, register } from "./api";
import { CostPanel } from "./components/CostPanel";
import { EnrichForm } from "./components/EnrichForm";
import { ResultsPanel } from "./components/ResultsPanel";
import { StrategyPanel } from "./components/StrategyPanel";
import type { LookupResult, ProviderStrategy, TokenResponse } from "./types";

function Shell({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        minHeight: "100vh",
        background: "#f8fafc",
        color: "#111827",
      }}
    >
      <div
        style={{
          borderBottom: "1px solid #e5e7eb",
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#ffffff",
        }}
      >
        <Link to="/" style={{ textDecoration: "none", color: "#111827", fontWeight: 650 }}>
          Lead enrichment dashboard
        </Link>
        <div style={{ display: "flex", gap: 12, fontSize: 14 }}>
          <Link to="/login">Login</Link>
          <Link to="/register">Register</Link>
        </div>
      </div>
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: 16 }}>{children}</div>
    </div>
  );
}

const tokenKey = "lead-enrichment-token";
const userKey = "lead-enrichment-user";

function useAuthState() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(tokenKey));
  const [email, setEmail] = useState<string | null>(() => localStorage.getItem(userKey));

  function saveAuth(resp: TokenResponse) {
    setToken(resp.access_token);
    setEmail(resp.user.email);
    localStorage.setItem(tokenKey, resp.access_token);
    localStorage.setItem(userKey, resp.user.email);
  }

  function logout() {
    setToken(null);
    setEmail(null);
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(userKey);
  }

  return { token, email, saveAuth, logout };
}

function Home({ token }: { token: string }) {
  const [lookupId, setLookupId] = useState<number | null>(null);
  const [result, setResult] = useState<LookupResult | null>(null);
  const [history, setHistory] = useState<LookupResult[]>([]);
  const [strategy, setStrategy] = useState<ProviderStrategy | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const progress = useMemo(() => {
    if (!result) return "Scrape";
    if (result.status === "running" || result.status === "queued") return "Scrape -> Email -> Phone -> Timeline";
    return "Done";
  }, [result]);

  useEffect(() => {
    Promise.all([listLookups(token), getStrategy(token)])
      .then(([lookups, strategyResp]) => {
        setHistory(lookups.items);
        setStrategy(strategyResp);
      })
      .catch(() => undefined);
  }, [token]);

  useEffect(() => {
    if (!lookupId) return;
    const t = setInterval(async () => {
      try {
        const next = await getLookup(lookupId, token);
        setResult(next);
        if (!["queued", "running"].includes(next.status)) {
          setBusy(false);
          clearInterval(t);
          const h = await listLookups(token);
          setHistory(h.items);
        }
      } catch {
        setBusy(false);
        clearInterval(t);
      }
    }, 2000);
    return () => clearInterval(t);
  }, [lookupId, token]);

  return (
    <div>
      <h2 style={{ margin: "16px 0 8px", fontSize: 22 }}>Enrich a LinkedIn profile</h2>
      <p style={{ margin: 0, color: "#6b7280" }}>
        Enter a LinkedIn URL to fetch profile, experience timeline, and contact info with source + cost
        tracking.
      </p>
      <div
        style={{
          marginTop: 16,
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: 16,
          background: "#fff",
        }}
      >
        <EnrichForm
          disabled={busy}
          onSubmit={async (linkedinUrl) => {
            setError(null);
            setBusy(true);
            try {
              const r = await enrich(linkedinUrl, token);
              setLookupId(r.lookupId);
              const initial = await getLookup(r.lookupId, token);
              setResult(initial);
              if (!["queued", "running"].includes(initial.status)) {
                setBusy(false);
                const h = await listLookups(token);
                setHistory(h.items);
              }
            } catch (e) {
              setBusy(false);
              setError(e instanceof Error ? e.message : "Failed to enrich");
            }
          }}
        />
        {error ? <div style={{ color: "#b91c1c", marginTop: 8 }}>{error}</div> : null}
        <div style={{ marginTop: 8, color: "#4b5563", fontSize: 13 }}>Progress: {progress}</div>
      </div>

      <div style={{ marginTop: 16, display: "grid", gap: 12 }}>
        <StrategyPanel strategy={strategy} />
        <ResultsPanel result={result} />
        <CostPanel result={result} />
      </div>

      <div style={{ marginTop: 16, border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, background: "#ffffff" }}>
        <h3 style={{ margin: "0 0 8px" }}>Lookup history</h3>
        <div style={{ display: "grid", gap: 8 }}>
          {history.length ? (
            history.map((h) => (
              <button
                key={h.id}
                style={{
                  textAlign: "left",
                  border: "1px solid #f3f4f6",
                  background: "white",
                  borderRadius: 8,
                  padding: 8,
                  cursor: "pointer",
                }}
                onClick={() => {
                  setLookupId(h.id);
                  setResult(h);
                }}
              >
                <div style={{ fontWeight: 600 }}>{h.linkedinUrl}</div>
                <div style={{ color: "#6b7280", fontSize: 13 }}>status: {h.status}</div>
              </button>
            ))
          ) : (
            <div style={{ color: "#6b7280" }}>No lookups yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function AuthPage({
  mode,
  onSubmit,
}: {
  mode: "login" | "register";
  onSubmit: (email: string, password: string) => Promise<void>;
}) {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        try {
          await onSubmit(email, password);
          nav("/");
        } catch (err) {
          setError(err instanceof Error ? err.message : "Auth failed");
        }
      }}
      style={{ maxWidth: 420, display: "grid", gap: 8 }}
    >
      <h2 style={{ marginTop: 8 }}>{mode === "login" ? "Login" : "Register"}</h2>
      <input
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #d1d5db" }}
      />
      <input
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        type="password"
        placeholder="Password"
        style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #d1d5db" }}
      />
      <button
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "1px solid #111827",
          background: "#111827",
          color: "white",
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        {mode === "login" ? "Login" : "Create Account"}
      </button>
      {error ? <div style={{ color: "#b91c1c" }}>{error}</div> : null}
    </form>
  );
}

function Guard({ token, children }: { token: string | null; children: ReactNode }) {
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const auth = useAuthState();

  return (
    <Shell>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, color: "#4b5563", fontSize: 13 }}>
        <div>{auth.email ? `Signed in as ${auth.email}` : "Not signed in"}</div>
        {auth.token ? (
          <button style={{ border: "none", background: "transparent", cursor: "pointer", textDecoration: "underline" }} onClick={auth.logout}>
            Logout
          </button>
        ) : null}
      </div>
      <Routes>
        <Route
          path="/"
          element={
            <Guard token={auth.token}>
              <Home token={auth.token!} />
            </Guard>
          }
        />
        <Route
          path="/login"
          element={
            <AuthPage
              mode="login"
              onSubmit={async (email, password) => {
                auth.saveAuth(await login(email, password));
              }}
            />
          }
        />
        <Route
          path="/register"
          element={
            <AuthPage
              mode="register"
              onSubmit={async (email, password) => {
                auth.saveAuth(await register(email, password));
              }}
            />
          }
        />
      </Routes>
    </Shell>
  );
}
