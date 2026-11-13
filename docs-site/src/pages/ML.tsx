import { FEATURES, QUOTE_WIN_FEATURES, PROMPTS } from '../data/extra'
import { PageHeader, Callout, Src, StatusBadge } from '../components/ui'

const Flow = ({ steps, label }: { steps: string[]; label: string }) => (
  <ol className="flow" aria-label={label}>
    {steps.map((s) => <li key={s}>{s}</li>)}
  </ol>
)

export default function ML() {
  return (
    <section className="page">
      <PageHeader eyebrow="Machine Learning" title="Semantic retrieval, ranking, and B2B pricing" lead="Four specialized ML components with bounded responsibilities. None of them decides schedule feasibility or overrides business safety guardrails." />

      {/* 1. Multilingual E5 Semantic Search */}
      <h2>1. Semantic retrieval (Multilingual E5) <StatusBadge status="partial" /></h2>
      <Flow label="Semantic retrieval" steps={['Traveler Query', 'multilingual-e5-base (CPU)', 'Cosine Similarity', 'Candidate Retrieval']} />
      <p>Used by <code>GET /api/experience-search?semantic=true</code>. Queries are prefixed <code>query:</code> and catalog passages <code>passage:</code>. Model inference runs strictly locally on CPU with <code>local_files_only=True</code>, ensuring zero traveler query leakage to external third-party cloud APIs. Source: <Src path="apps/api/app/services/e5_search_service.py" />.</p>
      <Callout tone="note" title="Setup & Download">
        Model weights are downloadable via <Src path="scripts/download_e5_model.py" />. When model weights are absent or optional ML dependencies are not installed, the catalog automatically falls back to keyword and tag filtering.
      </Callout>

      {/* 2. Candidate Ranker */}
      <h2>2. Candidate ranker (Baseline & XGBoost pilot) <StatusBadge status="experimental" /></h2>
      <Flow label="Ranking" steps={['Feasible Candidates', '15 Features (ranker-features-v2)', 'Tie-Break Ranker', 'Ordered Schedule']} />
      <p>The candidate ranker breaks ties among feasible candidates at the earliest available time slot. <strong>Production default active model is <code>rule-baseline-v1</code></strong>. An experimental XGBoost model (<code>rank:ndcg</code>) is maintained as a research pilot.</p>
      
      <div className="table-wrap">
        <table>
          <caption className="sr-only">The 15 candidate ranker features</caption>
          <thead><tr><th>#</th><th>Feature Name</th><th>Semantic Meaning</th></tr></thead>
          <tbody>
            {FEATURES.map(([n, t], i) => (
              <tr key={n}>
                <td>{i + 1}</td>
                <th scope="row" className="mono">{n}</th>
                <td>{t}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="dim">Feature definitions in <Src path="apps/api/app/services/ranker_features.py" />.</p>
      
      <Callout tone="warn" title="Weak-Label Safety Gate">
        The ranking training dataset in <code>data/ranking/</code> has synthetic weak labels without human ground-truth provenance (<code>dataset_status=weak_synthetic</code>). Consequently, production strictly loads <code>rule-baseline-v1</code> by default, quarantining the XGBoost model unless explicitly overridden with <code>ALLOW_UNVERIFIED_RANKER=true</code>.
      </Callout>

      {/* 3. B2B Tour Quote Win-Rate Model */}
      <h2>3. Tour quote win-rate model (B2B Pricing) <StatusBadge status="experimental" /></h2>
      <Flow label="Quote Win Optimization" steps={['RFP Parameters', 'Rate-Card Matrix', '18 Win Features', 'XGBoost P(win)', 'MarginGuard Check']} />
      <p>Predicts client acceptance probability <code>P(win)</code> for corporate and agency tour quotations across 18 features, allowing the pricing optimizer to maximize expected margin without pricing out prospective clients.</p>
      
      <div className="table-wrap">
        <table>
          <caption className="sr-only">The 18 quote win model features</caption>
          <thead><tr><th>#</th><th>Feature Parameter</th><th>Description</th></tr></thead>
          <tbody>
            {QUOTE_WIN_FEATURES.map(([n, t], i) => (
              <tr key={n}>
                <td>{i + 1}</td>
                <th scope="row" className="mono">{n}</th>
                <td>{t}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ color: 'var(--cyan)' }}>Test Set Backtest Results (3,622 Test Quotes)</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Pricing Strategy</th>
                <th>Expected Profit (VND)</th>
                <th>Vs Fixed 25% Markup</th>
                <th>Expected Win Rate</th>
                <th>Avg Quoted Margin</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">fixed_25pct_markup</th>
                <td>5,449,526,147 ₫</td>
                <td>+0.0% (Baseline)</td>
                <td>31.7%</td>
                <td>20.5%</td>
              </tr>
              <tr style={{ background: 'rgba(34, 211, 238, 0.08)' }}>
                <th scope="row" style={{ color: 'var(--cyan)' }}>optimizer_balanced (Active)</th>
                <td style={{ fontWeight: 600, color: 'var(--green)' }}>5,968,957,526 ₫</td>
                <td style={{ fontWeight: 600, color: 'var(--green)' }}>+9.5%</td>
                <td>24.6%</td>
                <td>26.6%</td>
              </tr>
              <tr>
                <th scope="row">optimizer_max_profit</th>
                <td>5,846,774,251 ₫</td>
                <td>+7.3%</td>
                <td>20.9%</td>
                <td>29.4%</td>
              </tr>
              <tr>
                <th scope="row">oracle_max_profit (True P)</th>
                <td>6,273,466,859 ₫</td>
                <td>+15.1% (Theoretical)</td>
                <td>27.4%</td>
                <td>24.2%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="dim small" style={{ marginTop: 8 }}>
          <strong>Extrapolation Guard:</strong> Unconstrained tree models extrapolation beyond training boundaries caused a 5.9% loss in legacy prototypes. The production optimizer strictly enforces price grid boundaries (<Src path="price_support.price_ratio_cost_max" />) and corporate margin floors via <Src path="apps/api/app/services/quote/margin_guard.py" />.
        </p>
      </div>

      {/* 4. Explainability */}
      <h2>4. Explainability & Trust Metrics</h2>
      <p>Itinerary responses carry an <code>explanation</code> payload: <code>reason_codes</code>, <code>preserved_intents</code>, <code>lost_intents</code>, <code>uncertainty</code>, and <code>data_status</code> (verified, stale, simulated, or unverified).</p>
      <div className="why" role="group" aria-label="Illustrative explanation (not model output)">
        <p className="mono dim">Illustrative Decision Attribution Score</p>
        {[
          ['Semantic relevance', 'High', 92],
          ['Time slot fit', 'High', 88],
          ['Transport ETA', 'Low', 20],
          ['Verified capacity', 'High', 95],
          ['Margin floor margin', 'Optimal', 85],
        ].map(([k, v, w]) => (
          <div className="meter" key={k as string}>
            <span>{k}</span>
            <span className="bar"><i style={{ width: `${w}%` }} /></span>
            <strong>{v}</strong>
          </div>
        ))}
      </div>

      {/* 5. Flood Risk Model */}
      <h2>5. Flood risk model (Offline Research Prototype) <StatusBadge status="partial" /></h2>
      <p><code>POST /api/ml/flood-risk</code> serves batch segment probability inference. When coverage observation is missing, the response explicitly defaults to <code>unknown</code> rather than assuming safety.</p>
      <Callout tone="warn" title="Prototype Status">
        Flood model weights are not committed to git and are not wired into the active road routing graph.
      </Callout>

      {/* 6. Prompt Catalog v3.2.0 */}
      <h2>6. Prompt catalog v3.2.0 (20 Specialized Workflows)</h2>
      <p>Every prompt is versioned in Markdown and returns strictly validated Pydantic models. When an LLM API key is not configured, the service falls back to deterministic rule extraction.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Prompt Workflow ID</th><th>Specialized Purpose & Output Schema</th></tr></thead>
          <tbody>
            {PROMPTS.map(([n, t]) => (
              <tr key={n}>
                <th scope="row" className="mono">{n}</th>
                <td>{t}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="dim">Prompts stored in <Src path="apps/api/app/prompts/v3_2_0/" />.</p>
    </section>
  )
}
