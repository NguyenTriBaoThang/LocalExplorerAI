import { FEATURES, PROMPTS } from '../data/extra'
import { PageHeader, Callout, Src, StatusBadge } from '../components/ui'

const Flow = ({ steps, label }: { steps: string[]; label: string }) => (
  <ol className="flow" aria-label={label}>
    {steps.map((s) => <li key={s}>{s}</li>)}
  </ol>
)

export default function ML() {
  return (
    <section className="page">
      <PageHeader eyebrow="Machine Learning" title="Retrieval, ranking and risk" lead="Three local models, each with a narrow role. None of them decides whether an itinerary is feasible." />

      <h2>Semantic retrieval <StatusBadge status="partial" /></h2>
      <Flow label="Semantic retrieval" steps={['Query', 'E5 embedding (CPU)', 'Vector similarity', 'Relevant candidates']} />
      <p>Used by <code>GET /api/experience-search?semantic=true</code>. Queries are prefixed <code>query:</code> and passages <code>passage:</code>, and the model is loaded with <code>local_files_only=True</code>, so inference never reaches the network. Source: <Src path="apps/api/app/services/e5_search_service.py" />.</p>
      <Callout tone="warn" title="Setup required">The semantic mode needs the optional dependencies and a local <code>multilingual-e5-base</code> directory set in <code>E5_MODEL_PATH</code>. Without it the service raises <code>E5NotConfigured</code>. <code>models/e5/</code> in the repository is empty.</Callout>

      <h2>Ranking <StatusBadge status="partial" /></h2>
      <Flow label="Ranking" steps={['Candidates', '13 features', 'XGBRanker', 'Ranked results']} />
      <p>An <code>XGBRanker</code> with objective <code>rank:ndcg</code>. The planner uses it only as a tie-break among candidates at the earliest feasible time, and replanning uses it after database checks. Hard filters (budget, return deadline, slot, capacity, locked items) remain authoritative. If no bundle loads, the heuristic is used.</p>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">The 13 ranker features</caption>
          <thead><tr><th>#</th><th>Feature</th><th>Meaning</th></tr></thead>
          <tbody>{FEATURES.map(([n, t], i) => <tr key={n}><td>{i + 1}</td><th scope="row" className="mono">{n}</th><td>{t}</td></tr>)}</tbody>
        </table>
      </div>
      <p className="dim">Feature names are <code>FEATURE_NAMES</code> in <Src path="apps/api/app/services/ranker_features.py" />.</p>
      <Callout tone="warn" title="About the reported metric">
        The README reports NDCG@5 = 0.9516. <code>docs/ml-training-and-data.md</code> states that the training CSV (877 rows, 170 query groups) has no source, timestamp, reviewer or label-method fields, and treats the metric as a pipeline check, not evidence of real-world quality. Metadata must say <code>verified_human_labeled</code> for production to load the model, otherwise it is refused unless <code>ALLOW_UNVERIFIED_RANKER=true</code>. The trained weights are git-ignored, and <code>models/ai-ranker/</code> is empty in the repository.
      </Callout>

      <h2>Explainability</h2>
      <p>Itinerary responses carry an <code>explanation</code> object: <code>reason_codes</code>, <code>preserved_intents</code>, <code>lost_intents</code>, <code>uncertainty</code>, <code>evidence_refs</code> and <code>ranking_model_version</code>. Each stop also exposes <code>availability_status</code> and <code>data_status</code> (verified, stale, simulated or unverified).</p>
      <div className="why" role="group" aria-label="Illustrative explanation (not model output)">
        <p className="mono dim">Why this result? — illustrative example, not model output</p>
        {[['Semantic relevance', 'High', 92], ['Time compatibility', 'High', 88], ['Distance', 'Low', 20], ['Availability', 'High', 95]].map(([k, v, w]) => (
          <div className="meter" key={k as string}><span>{k}</span><span className="bar"><i style={{ width: `${w}%` }} /></span><strong>{v}</strong></div>
        ))}
      </div>

      <h2>Flood risk <StatusBadge status="partial" /></h2>
      <p><code>POST /api/ml/flood-risk</code> returns a probability per road segment, decision time and horizon. Without <code>coverage_ratio</code> the state is <code>unknown</code>: a missing report is never read as “no flood”. A prediction is not a verified closure and cannot override a hard block.</p>
      <Callout tone="warn" title="Limits">No flood model bundle is committed, and the API serves predictions but does not use them in routing. The public flood dataset in <code>data/raw/</code> contains reports only, with no verified negatives, so it is not training-ready.</Callout>

      <h2>Prompt catalog (version 3.0.0)</h2>
      <div className="table-wrap">
        <table><thead><tr><th>Prompt</th><th>Purpose</th></tr></thead>
          <tbody>{PROMPTS.map(([n, t]) => <tr key={n}><th scope="row" className="mono">{n}</th><td>{t}</td></tr>)}</tbody></table>
      </div>
      <p className="dim">Outputs are validated with Pydantic before use. Files in <Src path="apps/api/app/prompts/v3_0_0/" />.</p>
    </section>
  )
}
