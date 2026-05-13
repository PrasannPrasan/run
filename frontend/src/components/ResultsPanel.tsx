import type { LookupField, LookupResult } from "../types";

const rows: Array<[string, string]> = [
  ["Full Name", "full_name"],
  ["Current Company", "current_company"],
  ["Current Designation", "current_designation"],
  ["Total Years of Experience", "total_years_experience"],
  ["Email Address(es)", "emails"],
  ["Phone Number(s)", "phones"],
];

function field(result: LookupResult, key: string) {
  return result.fields[key];
}

function valueToText(v: unknown): string {
  if (v == null) return "-";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "-";
  return String(v);
}

function confidencePercent(fieldValue?: LookupField) {
  return Math.round((fieldValue?.confidence ?? 0) * 100);
}

function SourceList({ sources }: { sources: Array<{ provider: string; note?: string | null }> }) {
  if (!sources.length) return <span className="muted">No source yet</span>;

  return (
    <div className="source-list">
      {sources.map((source, index) => (
        <span key={`${source.provider}-${index}`}>
          {source.provider}
          {source.note ? `: ${source.note}` : ""}
        </span>
      ))}
    </div>
  );
}

export function ResultsPanel({ result }: { result: LookupResult | null }) {
  if (!result) {
    return (
      <section className="panel panel-empty">
        <div>
          <span className="eyebrow">Results</span>
          <h2>Contact snapshot</h2>
          <p>Run a lookup to see profile fields, confidence scores, source notes, and work history.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="results-layout">
      <div className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Results</span>
            <h2>Contact snapshot</h2>
          </div>
          <span className={`status-chip status-${result.status}`}>{result.status}</span>
        </div>
        <div className="field-grid">
          {rows.map(([label, key]) => {
            const item = field(result, key);
            const confidence = confidencePercent(item);
            return (
              <article className="field-card" key={key}>
                <div className="field-topline">
                  <span>{label}</span>
                  <strong>{confidence}%</strong>
                </div>
                <div className="field-value">{valueToText(item?.value)}</div>
                <div className="confidence-bar">
                  <span style={{ width: `${confidence}%` }} />
                </div>
                <SourceList sources={item?.sources || []} />
              </article>
            );
          })}
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Timeline</span>
            <h2>Work history</h2>
          </div>
          <span className="count-pill">{result.workHistory.length} roles</span>
        </div>
        <div className="timeline">
          {result.workHistory.length ? (
            result.workHistory.map((work, index) => (
              <article className="timeline-item" key={`${work.company}-${work.title}-${index}`}>
                <span className="timeline-marker" />
                <div>
                  <strong>
                    {work.title || "Unknown title"} at {work.company || "Unknown company"}
                  </strong>
                  <small>
                    {work.startDate || "?"} - {work.endDate || (work.isCurrent ? "Present" : "?")} -{" "}
                    {Math.round(work.confidence * 100)}% - {work.provider}
                  </small>
                </div>
              </article>
            ))
          ) : (
            <div className="empty-state">No timeline entries yet.</div>
          )}
        </div>
      </div>
    </section>
  );
}
