import type { LookupResult } from "../types";

export function CostPanel({ result }: { result: LookupResult | null }) {
  const successful = Boolean(
    result &&
      ((Array.isArray(result.fields.emails?.value) && result.fields.emails.value.length) ||
        (Array.isArray(result.fields.phones?.value) && result.fields.phones.value.length)),
  );
  const totalUsd = result?.costs.reduce((sum, c) => sum + (c.costUsd || 0), 0) ?? 0;
  const perSuccess = successful ? totalUsd : null;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Spend</span>
          <h2>Cost tracking</h2>
        </div>
        <span className="count-pill">${totalUsd.toFixed(4)}</span>
      </div>
      <div className="cost-metrics">
        <div>
          <span>Total USD</span>
          <strong>${totalUsd.toFixed(4)}</strong>
        </div>
        <div>
          <span>Per successful contact</span>
          <strong>{perSuccess == null ? "-" : `$${perSuccess.toFixed(4)}`}</strong>
        </div>
      </div>
      <div className="cost-list">
        {result?.costs.length ? (
          result.costs.map((cost, index) => (
            <article className="cost-item" key={`${cost.provider}-${index}`}>
              <div>
                <strong>{cost.provider}</strong>
                <small>
                  {cost.isEstimated ? "Estimated" : "Exact"} {cost.note ? `- ${cost.note}` : ""}
                </small>
              </div>
              <span>
                {cost.costUsd == null ? "-" : `$${cost.costUsd.toFixed(4)}`}
                {cost.costUnits ? ` - ${cost.costUnits} ${cost.unitName || "units"}` : ""}
              </span>
            </article>
          ))
        ) : (
          <div className="empty-state">Cost entries will appear after a lookup runs.</div>
        )}
      </div>
    </section>
  );
}
