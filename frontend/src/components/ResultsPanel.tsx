import type { LookupResult } from "../types";

function field(result: LookupResult, key: string) {
  return result.fields[key];
}

function valueToText(v: unknown): string {
  if (v == null) return "-";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

function SourceList({ sources }: { sources: Array<{ provider: string; note?: string | null }> }) {
  return (
    <div style={{ fontSize: 12, color: "#6b7280" }}>
      {sources.length ? sources.map((s, i) => <div key={`${s.provider}-${i}`}>{s.provider}: {s.note || "matched"}</div>) : "-"}
    </div>
  );
}

export function ResultsPanel({ result }: { result: LookupResult | null }) {
  if (!result) return null;

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, background: "#ffffff" }}>
        <h3 style={{ margin: "0 0 8px" }}>Contact snapshot</h3>
        {[
          ["Full Name", "full_name"],
          ["Current Company", "current_company"],
          ["Current Designation", "current_designation"],
          ["Total Years of Experience", "total_years_experience"],
          ["Email(s)", "emails"],
          ["Phone(s)", "phones"],
        ].map(([label, key]) => {
          const f = field(result, key);
          return (
            <div key={key} style={{ padding: "8px 0", borderTop: "1px solid #f3f4f6" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <strong>{label}</strong>
                <span style={{ fontSize: 12, color: "#374151" }}>
                  confidence: {f?.confidence ?? 0}
                </span>
              </div>
              <div>{valueToText(f?.value)}</div>
              <SourceList sources={f?.sources || []} />
            </div>
          );
        })}
      </div>

      <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, background: "#ffffff" }}>
        <h3 style={{ margin: "0 0 8px" }}>Work history timeline</h3>
        <div style={{ display: "grid", gap: 8 }}>
          {result.workHistory.length ? (
            result.workHistory.map((w, i) => (
              <div key={i} style={{ border: "1px solid #f3f4f6", borderRadius: 8, padding: 10 }}>
                <div style={{ fontWeight: 600 }}>{w.title || "Unknown title"} @ {w.company || "Unknown company"}</div>
                <div style={{ color: "#6b7280", fontSize: 13 }}>
                  {w.startDate || "?"} - {w.endDate || (w.isCurrent ? "Present" : "?")} | confidence {w.confidence}
                </div>
              </div>
            ))
          ) : (
            <div style={{ color: "#6b7280" }}>No timeline entries yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
