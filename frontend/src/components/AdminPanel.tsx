import { useEffect, useMemo, useState } from "react";
import { deleteAdminLookup, getAdminOverview, isAuthError, resetAdminLookup } from "../api";
import type { AdminOverview } from "../types";

function trimError(message?: string | null) {
  if (!message) return "-";
  const firstLine = message.split("\n")[0];
  return firstLine.length > 160 ? `${firstLine.slice(0, 157)}...` : firstLine;
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

export function AdminPanel({
  token,
  onAuthExpired,
}: {
  token: string;
  onAuthExpired: () => void;
}) {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const totals = useMemo(() => {
    const lookups = overview?.lookups ?? [];
    return {
      users: overview?.users.length ?? 0,
      lookups: lookups.length,
      failed: lookups.filter((lookup) => lookup.status === "failed").length,
      cost: lookups.reduce((sum, lookup) => sum + (lookup.totalCostUsd || 0), 0),
    };
  }, [overview]);

  async function load() {
    setError(null);
    try {
      setOverview(await getAdminOverview(token));
    } catch (err) {
      if (isAuthError(err)) {
        onAuthExpired();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load admin data");
    }
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function runAction(lookupId: number, action: "delete" | "reset") {
    setBusyId(lookupId);
    setError(null);
    try {
      if (action === "delete") {
        await deleteAdminLookup(lookupId, token);
      } else {
        await resetAdminLookup(lookupId, token);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Admin action failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="dashboard admin-page">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Admin</span>
            <h2>Operations dashboard</h2>
          </div>
          <button className="ghost-button" type="button" onClick={load}>
            Refresh
          </button>
        </div>
        {error ? <div className="alert error">{error}</div> : null}
        <div className="summary-grid">
          <div className="summary-card">
            <span>Users</span>
            <strong>{totals.users}</strong>
          </div>
          <div className="summary-card">
            <span>Lookups</span>
            <strong>{totals.lookups}</strong>
          </div>
          <div className="summary-card">
            <span>Failed</span>
            <strong>{totals.failed}</strong>
          </div>
          <div className="summary-card">
            <span>Total cost</span>
            <strong>${totals.cost.toFixed(4)}</strong>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Providers</span>
            <h2>Status and errors</h2>
          </div>
        </div>
        <div className="admin-grid">
          {overview?.providerStatus.map((provider) => (
            <article className="provider-card" key={provider.provider}>
              <div className="provider-topline">
                <strong>{provider.provider}</strong>
                <span className={provider.enabled ? "provider-state enabled" : "provider-state missing"}>
                  {provider.enabled ? "key set" : "missing key"}
                </span>
              </div>
              <p>
                Logged calls: {provider.successes} returned - {provider.failures} missed
              </p>
              <small>{trimError(provider.latestError)}</small>
            </article>
          )) ?? <div className="empty-state">Loading provider status.</div>}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Users</span>
            <h2>All users</h2>
          </div>
        </div>
        <div className="admin-table">
          <div className="admin-row admin-row-head">
            <span>Email</span>
            <span>Lookups</span>
            <span>Created</span>
          </div>
          {overview?.users.map((user) => (
            <div className="admin-row" key={user.id}>
              <span>{user.email}</span>
              <span>{user.lookupCount}</span>
              <span>{formatDate(user.createdAt)}</span>
            </div>
          )) ?? <div className="empty-state">Loading users.</div>}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Lookups</span>
            <h2>All lookups</h2>
          </div>
        </div>
        <div className="admin-lookup-list">
          {overview?.lookups.map((lookup) => (
            <article className="admin-lookup" key={lookup.id}>
              <div className="admin-lookup-main">
                <div>
                  <strong>{lookup.linkedinUrl}</strong>
                  <small>{lookup.userEmail || "Unknown user"} - {formatDate(lookup.createdAt)}</small>
                </div>
                <span className={`status-chip status-${lookup.status}`}>{lookup.status}</span>
              </div>
              <div className="admin-lookup-meta">
                <span>Cost ${lookup.totalCostUsd.toFixed(4)}</span>
                <span>{lookup.providerCalls.length} provider calls</span>
              </div>
              <div className="provider-diagnostics compact">
                {lookup.providerCalls.map((call, index) => (
                  <article className="diagnostic-item" key={`${lookup.id}-${call.provider}-${index}`}>
                    <div>
                      <strong>{call.provider}</strong>
                      <small>{call.stage}</small>
                    </div>
                    <span className={call.success ? "provider-state enabled" : "provider-state missing"}>
                      {call.success ? "returned" : "missed"}
                    </span>
                    {call.errorMessage ? <p>{trimError(call.errorMessage)}</p> : null}
                  </article>
                ))}
              </div>
              <div className="admin-actions">
                <button
                  className="ghost-button"
                  type="button"
                  disabled={busyId === lookup.id}
                  onClick={() => runAction(lookup.id, "reset")}
                >
                  {lookup.status === "failed" ? "Reset failed" : "Rerun"}
                </button>
                <button
                  className="danger-button"
                  type="button"
                  disabled={busyId === lookup.id}
                  onClick={() => runAction(lookup.id, "delete")}
                >
                  Delete
                </button>
              </div>
            </article>
          )) ?? <div className="empty-state">Loading lookups.</div>}
        </div>
      </section>
    </div>
  );
}
