import { useState } from 'react'
import { CHAT_EXAMPLES } from '../data/extra'
import { DemoLabel, PageHeader, Callout, Src } from '../components/ui'

export default function Concierge() {
  const [id, setId] = useState(CHAT_EXAMPLES[0].id)
  const ex = CHAT_EXAMPLES.find((e) => e.id === id)!
  return (
    <section className="page">
      <PageHeader eyebrow="AI Concierge" title="From a sentence to constraints" lead="The concierge turns free text into a structured constraint object that feeds the planner. It does not choose places; that is the planner’s job." />
      <DemoLabel>no LLM is called</DemoLabel>
      <div className="chat-demo">
        <div className="chat">
          <div className="chips" role="group" aria-label="Example prompts">
            {CHAT_EXAMPLES.map((e) => (
              <button key={e.id} type="button" className={e.id === id ? 'chip on' : 'chip'} aria-pressed={e.id === id} onClick={() => setId(e.id)}>{e.label}</button>
            ))}
          </div>
          <div className="bubble user"><span className="mono dim">User</span>{ex.prompt}</div>
          <div className="bubble bot"><span className="mono dim">Concierge (sample reply)</span>{ex.reply}</div>
        </div>
        <aside className="inspector" aria-live="polite">
          <h3>Extracted constraints</h3>
          <dl>
            {ex.constraints.map(([k, v], i) => (
              <div key={i} className={k === 'Missing' ? 'row missing' : 'row'}><dt className="mono">{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
        </aside>
      </div>

      <h2>What the repository really does</h2>
      <ul className="plain">
        <li><code>POST /api/chat/message</code> runs the <code>CONVERSATION_PARSER</code> prompt and validates the result against a schema (<Src path="apps/api/app/api/routes/chat.py" />).</li>
        <li>With no LLM key configured and <code>LLM_FALLBACK_ENABLED</code> on, a local heuristic answers instead; the response says <code>status: "fallback"</code> and <code>assistant_mode: "local_fallback"</code>. <code>GET /api/chat/status</code> reports which mode is active.</li>
        <li>Chat is a traveler feature: signed-in non-travelers get <code>ROLE_FORBIDDEN</code>.</li>
        <li>Prompts are versioned (<code>3.0.0</code>) under <Src path="apps/api/app/prompts/v3_0_0/" />.</li>
      </ul>
      <Callout title="About the demo above">The prompts, replies and constraints are hand-written samples to illustrate the shape of the output. Real extraction depends on the configured model and prompt.</Callout>
    </section>
  )
}
