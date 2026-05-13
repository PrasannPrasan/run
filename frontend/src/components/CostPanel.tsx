import type { LookupResult } from "../types";

export function CostPanel({ result }: { result: LookupResult | null }) {
  if (!result) return null;
  const successful = Boolean(
    (result.fields.emails?.value && Array.isArray(result.fields.emails.value) && result.fields.emails.value.length) ||
      (result.fields.phones?.value && Array.isArray(result.fields.phones.value) && result.fields.phones.value.length),
  );

  const totalUsd = result.costs.reduce((sum, c) => sum + (c.costUsd || 0), 0);
  const perSuccess = successful ? totalUsd : null;

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, background: "#ffffff" }}>
      <h3 style={{ margin: "0 0 8px" }}>Cost tracking</h3>
      <div style={{ color: "#374151", marginBottom: 8 }}>
        Total USD: <strong>{totalUsd.toFixed(4)}</strong>
        {" | "}
        Cost per successful contact: <strong>{perSuccess == null ? "-" : perSuccess.toFixed(4)}</strong>
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        {result.costs.length ? (
          result.costs.map((c, i) => (
            <div key={`${c.provider}-${i}`} style={{ border: "1px solid #f3f4f6", borderRadius: 8, padding: 8 }}>
              <div style={{ fontWeight: 600 }}>{c.provider}</div>
              <div style={{ fontSize: 13, color: "#4b5563" }}>
                usd={c.costUsd ?? "-"}, units={c.costUnits ?? "-"} {c.unitName || ""}
              </div>
              <div style={{ fontSize: 12, color: "#6b7280" }}>
                {c.isEstimated ? "estimated" : "exact"}{c.note ? ` - ${c.note}` : ""}
              </div>
            </div>
          ))
        ) : (
          <div style={{ color: "#6b7280" }}>No cost records yet.</div>
        )}
      </div>
    </div>
  );
}
