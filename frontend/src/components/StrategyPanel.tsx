import type { ProviderStrategy } from "../types";

export function StrategyPanel({ strategy }: { strategy: ProviderStrategy | null }) {
  if (!strategy) {
    return (
      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Waterfall</span>
            <h2>Provider strategy</h2>
          </div>
        </div>
        <div className="empty-state">Loading provider configuration.</div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Waterfall</span>
          <h2>Provider strategy</h2>
        </div>
        <span className="count-pill">
          {strategy.providers.filter((p) => p.enabled).length}/{strategy.providers.length} enabled
        </span>
      </div>

      <div className="waterfall-order">{strategy.recommendedOrder.join(" -> ")}</div>

      <div className="provider-grid">
        {strategy.providers.map((provider) => (
          <a className="provider-card" key={provider.name} href={provider.sourceUrl} target="_blank" rel="noreferrer">
            <div className="provider-topline">
              <strong>{provider.name}</strong>
              <span className={provider.enabled ? "provider-state enabled" : "provider-state missing"}>
                {provider.enabled ? "key set" : "missing key"}
              </span>
            </div>
            <p>{provider.bestFor}</p>
            <small>{provider.costModel}</small>
          </a>
        ))}
      </div>

      <div className="logic-list">
        {strategy.logic.slice(0, 4).map((item) => (
          <div key={item}>{item}</div>
        ))}
      </div>
      <p className="compliance-note">{strategy.complianceNote}</p>
    </section>
  );
}
