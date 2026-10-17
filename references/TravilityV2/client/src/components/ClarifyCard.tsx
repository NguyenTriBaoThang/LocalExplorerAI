import { useState } from 'react'
import { toAnswers, type Answers, type Question } from '../api'

export default function ClarifyCard({ questions, busy, onSubmit }: {
  questions: Question[]; busy: boolean; onSubmit: (answers: Answers) => void
}) {
  const [form, setForm] = useState<Record<string, string>>({})
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }))
  const chip = (k: string, v: string, label: string) => (
    <button key={v} type="button" aria-pressed={form[k] === v} onClick={() => set(k, form[k] === v ? '' : v)}
      className={`rounded-full border px-3 py-1 text-xs ${form[k] === v
        ? 'border-emerald-700 bg-emerald-700 text-white' : 'border-stone-300 bg-white'}`}>{label}</button>
  )
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-3 text-sm">
      {questions.map((q) => (
        <fieldset key={q.field} className="flex flex-col gap-2">
          <legend className="mb-1">{q.text}</legend>
          <div className="flex flex-wrap gap-1">
            {q.options.map((o) => chip(q.field === 'arrival' ? 'arrival_mode' : q.field, o.value, o.label))}
          </div>
          {q.field === 'arrival' && (
            <div className="flex gap-3 text-xs">
              <label className="flex items-center gap-1">Tới lúc
                <input type="time" className="rounded border border-stone-300 px-1"
                  value={form.arrival_time ?? ''} onChange={(e) => set('arrival_time', e.target.value)} />
              </label>
              <label className="flex items-center gap-1">Về lúc
                <input type="time" className="rounded border border-stone-300 px-1"
                  value={form.departure_time ?? ''} onChange={(e) => set('departure_time', e.target.value)} />
              </label>
            </div>
          )}
        </fieldset>
      ))}
      <div className="flex gap-2">
        <button disabled={busy} onClick={() => onSubmit(toAnswers(form))}
          className="rounded-lg bg-emerald-700 px-3 py-1.5 text-white disabled:opacity-50">Lên lịch</button>
        <button disabled={busy} onClick={() => onSubmit({})}
          className="rounded-lg border border-stone-300 px-3 py-1.5 disabled:opacity-50">Bỏ qua, cứ lên lịch</button>
      </div>
    </div>
  )
}
