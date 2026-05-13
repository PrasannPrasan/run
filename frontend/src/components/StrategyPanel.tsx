import type { ProviderStrategy } from "../types";

export function StrategyPanel({ strategy }: { strategy: ProviderStrategy | null }) {
  if (!strategy) return null;

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, background: "#ffffff" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: "0 0 4px", fontSize: 16 }}>Provider waterfall</h3>
          <div style={{ color: "#4b5563", fontSize: 13 }}>{strategy.recommendedOrder.join(" -> ")}</div>
        </div>
        <div style={{ color: "#374151", fontSize: 13 }}>
          Enabled: {strategy.providers.filter((p) => p.enabled).length}/{strategy.providers.length}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 8, marginTop: 12 }}>
        {strategy.providers.map((provider) => (
          <a
            key={provider.name}
            href={provider.sourceUrl}
            target="_blank"
            rel="noreferrer"
            style={{
              border: "1px solid #f3f4f6",
              borderRadius: 8,
              padding: 10,
              color: "#111827",
              textDecoration: "none",
              background: provider.enabled ? "#f0fdf4" : "#fff7ed",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
              <strong style={{ textTransform: "capitalize" }}>{provider.name}</strong>
              <span
                style={{
                  border: "1px solid #d1d5db",
                  borderRadius: 999,
                  padding: "2px 8px",
                  fontSize: 12,
                  background: "#ffffff",
                }}
              >
                {provider.enabled ? "key set" : "missing key"}
              </span>
            </div>
            <div style={{ color: "#4b5563", fontSize: 13, marginTop: 6 }}>{provider.bestFor}</div>
            <div style={{ color: "#6b7280", fontSize: 12, marginTop: 6 }}>{provider.costModel}</div>
          </a>
        ))}
      </div>

      <div style={{ marginTop: 12, display: "grid", gap: 6 }}>
        {strategy.logic.slice(0, 4).map((item) => (
          <div key={item} style={{ color: "#374151", fontSize: 13 }}>
            {item}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 10, color: "#6b7280", fontSize: 12 }}>{strategy.complianceNote}</div>
    </div>
  );
}
