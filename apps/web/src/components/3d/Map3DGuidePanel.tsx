import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Bot, ChevronDown, LoaderCircle, MapPin, RotateCcw, Send, Sparkles, X } from 'lucide-react'
import { api, apiErrorMessage, sendChatMessage } from '../../api/client'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth'
import { useJourney, useAssistantField, chatContext } from '../../journey'
import { SourceDetails } from '../journey/SourceDetails'
import type { SourceEvidence } from '../../types'
import type { ModelCalibration } from './landmark/types'

type LandmarkContext = { poi_id: string | null; in_pilot: boolean; verified: boolean; description: string | null; notice: string; sources: SourceEvidence[]; experiences: { id: string; name: string; poi_id: string; data_mode: string }[] }

const makeConversationId = () => globalThis.crypto?.randomUUID?.() ?? `map-guide-${Date.now()}`

export function Map3DGuidePanel({ landmark, modelId }: { landmark: ModelCalibration; modelId: string }) {
  const { trip, applyConstraints, toggleExperience } = useJourney()
  const { user } = useAuth()
  const [context, setContext] = useState<LandmarkContext | null>(null)
  const [contextError, setContextError] = useState('')
  const [constraints, setConstraints] = useAssistantField('constraints')
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useAssistantField('busy')
  const [error, setError] = useState('')
  const [conversationId, setConversationId] = useAssistantField('conversationId')
  const [messages, setMessages] = useAssistantField('messages')
  const turns = messages.filter((message) => message.role === 'user')
  const feedRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    setContext(null)
    setContextError('')
    api.get<LandmarkContext>(`/journey/landmarks/${encodeURIComponent(modelId)}`, { params: { demo: trip.demo } })
      .then(({ data }) => { if (active) setContext(data) })
      .catch((reason) => { if (active) setContextError(apiErrorMessage(reason)) })
    return () => { active = false }
  }, [modelId, trip.demo])

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [messages, busy])

  function resetConversation() {
    setConversationId(makeConversationId())
    setConstraints(null)
    setError('')
    setDraft('')
    setMessages([{
      id: 'welcome',
      role: 'assistant',
      text: `Chào bạn! Mình đang cùng bạn xem **${landmark.display_name}**. Bạn muốn tìm hiểu địa điểm này, khám phá trải nghiệm văn hóa hay lên lịch tham quan?`,
    }])
  }

  async function sendMessage(rawText: string) {
    const text = rawText.trim()
    if (!text || busy) return

    setDraft('')
    setError('')
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', text }])
    setBusy(true)

    try {
      const result = await sendChatMessage(text, conversationId, { previous_constraints: chatContext(trip, constraints), model_id: modelId })
      if (result.structured_constraints) applyConstraints(result.structured_constraints)
      const reply = result.reply || result.structured_constraints?.clarification_question_vi || 'Bạn cho mình biết thêm thời gian và ngân sách để mình gợi ý phù hợp nhé.'
      setMessages((current) => [...current, { id: `assistant-${Date.now()}`, role: 'assistant', text: reply, assistantMode: result.assistant_mode === 'unavailable' ? undefined : result.assistant_mode }])
    } catch (reason) {
      setError(apiErrorMessage(reason) || 'Chưa kết nối được trợ lý. Bạn thử lại sau nhé.')
    } finally {
      setBusy(false)
    }
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void sendMessage(draft)
  }

  if (user && user.role !== 'traveler') return null

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="absolute top-20 right-3 z-30 inline-flex items-center gap-2 rounded-full border border-emerald-300/30 bg-slate-950/95 px-4 py-3 text-sm font-semibold text-white shadow-2xl shadow-black/40 backdrop-blur-xl transition hover:bg-slate-900"
        aria-label="Mở trợ lý khám phá"
      >
        <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-emerald-400 text-slate-950"><Bot size={18} /><span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-slate-950 bg-emerald-300" /></span>
        Hỏi trợ lý khám phá
      </button>
    )
  }

  return (
    <aside className="absolute inset-x-3 bottom-3 top-3 z-30 flex max-h-[min(720px,calc(100%-24px))] flex-col overflow-hidden rounded-2xl border border-white/15 bg-slate-950/95 text-slate-100 shadow-2xl shadow-slate-950/50 backdrop-blur-xl sm:inset-y-5 sm:left-auto sm:right-5 sm:w-[370px] sm:max-h-[calc(100%-40px)]" aria-label="Trợ lý khám phá bản đồ 3D">
      <header className="flex items-center gap-3 border-b border-white/10 bg-slate-900/90 px-4 py-3.5">
        <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-400 text-slate-950"><Bot size={21} /><span className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-slate-900 bg-emerald-300" /></div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-white">Trợ lý khám phá</h2>
          <p className="truncate text-[11px] text-slate-400">Đang xem · {landmark.display_name}</p>
        </div>
        <button type="button" onClick={resetConversation} disabled={busy} className="rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white" title="Bắt đầu cuộc trò chuyện mới" aria-label="Bắt đầu cuộc trò chuyện mới"><RotateCcw size={15} /></button>
        <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white" title="Thu gọn khung chat" aria-label="Thu gọn khung chat"><ChevronDown size={18} /></button>
      </header>

      <div className="border-b border-white/10 bg-emerald-400/[0.07] px-4 py-3">
        <div className="flex items-start gap-2.5">
          <MapPin size={15} className="mt-0.5 shrink-0 text-emerald-300" />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-white">{landmark.display_name}</p>
            <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-400">{context?.description || context?.notice || contextError || 'Đang đối chiếu mô hình với danh mục…'}</p>
            <p className="mt-1.5 font-mono text-[10px] text-slate-500">{landmark.latitude.toFixed(4)}, {landmark.longitude.toFixed(4)}</p>
          </div>
        </div>
      </div>

      <div className="space-y-2 border-b border-white/10 px-4 py-3 text-xs">
        <SourceDetails sources={context?.sources || []} />
        {context?.in_pilot && context.poi_id && <Link className="block text-emerald-300 underline" to={`/explore?poi_id=${encodeURIComponent(context.poi_id)}`}>Xem trải nghiệm tại địa danh này →</Link>}
        {context?.experiences.map((item) => <button key={item.id} type="button" className="block text-left text-emerald-300 underline" disabled={trip.selected.length >= 6 && !trip.selected.some((selected) => selected.id === item.id)} onClick={() => toggleExperience({ id: item.id, name: item.name, poiId: item.poi_id })}>
          {trip.selected.some((selected) => selected.id === item.id) ? 'Bỏ chọn' : 'Chọn'}: {item.name}{item.data_mode !== 'real' ? ' (mô phỏng)' : ''}
        </button>)}
        <Link className="block text-emerald-300 underline" to="/planner">Kiểm tra lịch trình đã chọn →</Link>
      </div>
      <div ref={feedRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3.5 py-4" aria-live="polite">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-5 ${message.role === 'user' ? 'rounded-br-md bg-emerald-400 font-medium text-slate-950' : 'rounded-bl-md border border-white/10 bg-slate-900 text-slate-200'}`}>
              {message.role === 'assistant' && <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-emerald-300"><Sparkles size={11} /> Local Explorer AI</div>}
              {message.text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith('**') && part.endsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> : part)}
            </div>
          </div>
        ))}
        {busy && <div className="flex items-center gap-2 px-2 text-xs text-slate-400"><LoaderCircle size={14} className="animate-spin text-emerald-300" /> Đang xem xét yêu cầu…</div>}
      </div>

      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2 border-t border-white/5 px-3.5 py-3">
          {['Kể tôi nghe về địa danh này', 'Gợi ý chuyến đi văn hóa', 'Tôi có 2 giờ để tham quan'].map((suggestion) => (
            <button key={suggestion} type="button" disabled={busy} onClick={() => void sendMessage(suggestion)} className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[10px] text-slate-300 transition hover:border-emerald-300/40 hover:bg-emerald-300/10 hover:text-white disabled:opacity-50">
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={submitMessage} className="border-t border-white/10 bg-slate-900/80 p-3">
        {error && <p className="mb-2 rounded-lg bg-rose-500/10 px-2.5 py-2 text-[11px] text-rose-200">{error}</p>}
        <div className="flex items-end gap-2 rounded-xl border border-white/10 bg-slate-950 px-2.5 py-2 focus-within:border-emerald-300/50">
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} rows={1} maxLength={700} placeholder="Hỏi về địa danh hoặc chuyến đi…" aria-label="Tin nhắn cho trợ lý khám phá" className="max-h-24 min-h-8 flex-1 resize-y bg-transparent px-1 py-1.5 text-xs leading-5 text-white outline-none placeholder:text-slate-500" />
          <button type="submit" disabled={!draft.trim() || busy} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-400 text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-40" aria-label="Gửi tin nhắn">{busy ? <LoaderCircle size={15} className="animate-spin" /> : <Send size={15} />}</button>
        </div>
        <p className="mt-2 flex items-center justify-between px-1 text-[9px] text-slate-500"><span>Enter để gửi · Shift + Enter xuống dòng</span><button type="button" onClick={() => setOpen(false)} className="inline-flex items-center gap-1 hover:text-slate-300"><X size={10} /> Thu gọn</button></p>
      </form>
    </aside>
  )
}
