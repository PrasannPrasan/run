import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { enrich, getLookup, getStrategy, isAuthError, listLookups, login, register } from "./api";
import { AdminPanel } from "./components/AdminPanel";
import { CostPanel } from "./components/CostPanel";
import { EnrichForm } from "./components/EnrichForm";
import { ResultsPanel } from "./components/ResultsPanel";
import { StrategyPanel } from "./components/StrategyPanel";
import type { LookupResult, ProviderStrategy, TokenResponse } from "./types";

const tokenKey = "lead-enrichment-token";
const userKey = "lead-enrichment-user";

function formatError(err: unknown, fallback = "Request failed") {
  return err instanceof Error ? err.message : fallback;
}

function Shell({
  children,
  email,
  onLogout,
}: {
  children: ReactNode;
  email: string | null;
  onLogout: () => void;
}) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">LE</span>
          <span>Lead Enrichment</span>
        </Link>
        <div className="topbar-actions">
          {email ? (
            <>
              <span className="user-pill">
                <span className="status-dot" />
                {email}
              </span>
              <Link to="/admin" className="nav-link">
                Admin
              </Link>
              <button className="ghost-button" type="button" onClick={onLogout}>
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link">
                Login
              </Link>
              <Link to="/register" className="primary-link">
                Register
              </Link>
            </>
          )}
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}

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

function ProgressRail({ result, busy }: { result: LookupResult | null; busy: boolean }) {
  const current = result?.status || (busy ? "running" : "ready");
  const steps = ["Scrape", "Contact match", "Timeline", "Cost log"];

  return (
    <div className="progress-rail" aria-label="Enrichment progress">
      {steps.map((step, index) => (
        <div className="progress-step" key={step}>
          <span className={index === 0 || busy || result ? "step-dot active" : "step-dot"} />
          <span>{step}</span>
        </div>
      ))}
      <span className={`status-chip status-${current}`}>{current}</span>
    </div>
  );
}

function Home({
  token,
  onAuthExpired,
}: {
  token: string;
  onAuthExpired: () => void;
}) {
  const [lookupId, setLookupId] = useState<number | null>(null);
  const [result, setResult] = useState<LookupResult | null>(null);
  const [history, setHistory] = useState<LookupResult[]>([]);
  const [strategy, setStrategy] = useState<ProviderStrategy | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const providerCount = useMemo(() => {
    const enabled = strategy?.providers.filter((p) => p.enabled).length ?? 0;
    const total = strategy?.providers.length ?? 4;
    return { enabled, total };
  }, [strategy]);

  const totalCost = useMemo(() => {
    if (!result) return 0;
    return result.costs.reduce((sum, cost) => sum + (cost.costUsd || 0), 0);
  }, [result]);

  useEffect(() => {
    Promise.all([listLookups(token), getStrategy(token)])
      .then(([lookups, strategyResp]) => {
        setHistory(lookups.items);
        setStrategy(strategyResp);
      })
      .catch((err) => {
        if (isAuthError(err)) onAuthExpired();
      });
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
      } catch (err) {
        setBusy(false);
        clearInterval(t);
        if (isAuthError(err)) {
          onAuthExpired();
          return;
        }
        setError(formatError(err, "Could not refresh lookup"));
      }
    }, 2000);
    return () => clearInterval(t);
  }, [lookupId, token]);

  async function runEnrichment(linkedinUrl: string) {
    setError(null);
    setBusy(true);
    try {
      const created = await enrich(linkedinUrl, token);
      setLookupId(created.lookupId);
      const initial = await getLookup(created.lookupId, token);
      setResult(initial);
      if (!["queued", "running"].includes(initial.status)) {
        setBusy(false);
        const h = await listLookups(token);
        setHistory(h.items);
      }
    } catch (err) {
      setBusy(false);
      if (isAuthError(err)) {
        onAuthExpired();
        return;
      }
      setError(formatError(err, "Failed to enrich profile"));
    }
  }

  return (
    <div className="dashboard">
      <section className="hero-panel">
        <div className="hero-copy">
          <div className="eyebrow">Multi-provider waterfall</div>
          <h1>Enrich LinkedIn leads with source and cost control</h1>
          <p>
            Run profile scraping, contact discovery, confidence scoring, and lookup cost tracking from one
            workspace.
          </p>
          <div className="summary-grid">
            <div className="summary-card">
              <span>Enabled providers</span>
              <strong>
                {providerCount.enabled}/{providerCount.total}
              </strong>
            </div>
            <div className="summary-card">
              <span>Saved lookups</span>
              <strong>{history.length}</strong>
            </div>
            <div className="summary-card">
              <span>Current lookup cost</span>
              <strong>${totalCost.toFixed(4)}</strong>
            </div>
          </div>
        </div>

        <div className="lookup-panel">
          <EnrichForm disabled={busy} onSubmit={runEnrichment} />
          {error ? <div className="alert error">{error}</div> : null}
          <ProgressRail busy={busy} result={result} />
        </div>
      </section>

      <div className="dashboard-grid">
        <StrategyPanel strategy={strategy} />
        <CostPanel result={result} />
      </div>

      <ResultsPanel result={result} />

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">History</span>
            <h2>Lookup history</h2>
          </div>
          <span className="count-pill">{history.length} saved</span>
        </div>
        <div className="history-list">
          {history.length ? (
            history.map((h) => (
              <button
                className="history-item"
                key={h.id}
                type="button"
                onClick={() => {
                  setLookupId(h.id);
                  setResult(h);
                }}
              >
                <span>
                  <strong>{h.linkedinUrl}</strong>
                  <small>{h.status}</small>
                </span>
                <span className={`status-chip status-${h.status}`}>{h.status}</span>
              </button>
            ))
          ) : (
            <div className="empty-state">No lookups yet. Add a LinkedIn URL above to start.</div>
          )}
        </div>
      </section>
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
  const isLogin = mode === "login";

  return (
    <div className="auth-layout">
      <section className="auth-copy">
        <div className="eyebrow">Secure workspace</div>
        <h1>{isLogin ? "Welcome back" : "Create your enrichment workspace"}</h1>
        <p>Sign in to run lookups, review provider sources, and keep a lookup history for repeat checks.</p>
      </section>
      <form
        className="auth-card"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            await onSubmit(email, password);
            nav("/");
          } catch (err) {
            setError(formatError(err, "Authentication failed"));
          }
        }}
      >
        <h2>{isLogin ? "Login" : "Register"}</h2>
        <label>
          <span>Email</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </label>
        <label>
          <span>Password</span>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            placeholder="Enter password"
          />
        </label>
        <button className="primary-button" type="submit">
          {isLogin ? "Login" : "Create Account"}
        </button>
        {error ? <div className="alert error">{error}</div> : null}
      </form>
    </div>
  );
}

function Guard({ token, children }: { token: string | null; children: ReactNode }) {
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const auth = useAuthState();
  const nav = useNavigate();
  const [notice, setNotice] = useState<string | null>(null);

  function handleLogout() {
    auth.logout();
    setNotice(null);
    nav("/login");
  }

  function handleAuthExpired() {
    auth.logout();
    setNotice("Your session was refreshed. Please login again.");
    nav("/login", { replace: true });
  }

  return (
    <Shell email={auth.email} onLogout={handleLogout}>
      {notice ? <div className="alert info">{notice}</div> : null}
      <Routes>
        <Route
          path="/"
          element={
            <Guard token={auth.token}>
              <Home token={auth.token!} onAuthExpired={handleAuthExpired} />
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
                setNotice(null);
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
                setNotice(null);
              }}
            />
          }
        />
        <Route
          path="/admin"
          element={
            <Guard token={auth.token}>
              <AdminPanel token={auth.token!} onAuthExpired={handleAuthExpired} />
            </Guard>
          }
        />
      </Routes>
    </Shell>
  );
}
