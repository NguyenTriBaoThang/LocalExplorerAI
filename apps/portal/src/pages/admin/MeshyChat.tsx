import { useState } from 'react'
import { http, errorMessage } from '../../lib/api'
type Message = { role: 'user' | 'assistant'; content: string }
export type ModelBrief = { reply: string; display_name: string; prompt: string; ready: boolean }
type Props = { images: string[]; reading: boolean; disabled: boolean; placeName: string; onImages: (files: FileList | null) => Promise<void>; onBrief: (brief: ModelBrief) => void; onInvalidate: () => void }
export function MeshyChat({ images, reading, disabled, placeName, onImages, onBrief, onInvalidate }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  async function send() {
    if (sending || disabled || reading || !input.trim()) return
    const next: Message[] = [...messages, { role: 'user', content: input.trim() }]
    setSending(true); setError(''); onInvalidate()
    try {
      const { data } = await http.post<ModelBrief>('/admin/meshy/chat', { messages: next.slice(-15), images, place_name: placeName }, { timeout: 65000 })
      setMessages([...next, { role: 'assistant', content: data.reply }]); setInput(''); onBrief(data)
    } catch (e) { setError(errorMessage(e)) } finally { setSending(false) }
  }
  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <header className="border-b border-slate-200 bg-violet-50 p-5"><h2 className="text-lg font-semibold text-violet-950">Trao đổi với Gemini</h2><p className="mt-1 text-sm text-slate-600">Gửi ảnh công trình và nói bạn muốn tạo gì. Gemini phân tích ảnh, hỏi thêm và chuẩn bị bản mô tả cho Meshy.</p></header>
    <div role="log" aria-label="Cuộc trò chuyện với Gemini" aria-live="polite" className="max-h-[440px] space-y-4 overflow-y-auto p-5">
      {!messages.length && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-700">Ví dụ: “Dựa vào ảnh này, hãy giúp tôi tạo mô hình toàn bộ tòa nhà, giữ mái và mặt tiền, bỏ cây và xe xung quanh.”</p>}
      {messages.map((m, i) => <div key={i} className={`max-w-[92%] rounded-xl p-4 ${m.role === 'user' ? 'ml-auto bg-indigo-50' : 'bg-stone-50'}`}><p className="mb-1 text-xs font-semibold text-slate-500">{m.role === 'user' ? 'Bạn' : 'Gemini'}</p><p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-900">{m.content}</p></div>)}
      {sending && <p role="status" className="text-sm text-violet-700">Gemini đang xem ảnh và chuẩn bị mô tả…</p>}
    </div>
    <div className="space-y-3 border-t border-slate-200 p-5">
      <div className="flex flex-wrap gap-2">{images.map((image, i) => <figure key={i}><img src={image} alt={`Ảnh tham chiếu ${i+1}`} className="h-24 w-28 rounded-lg border object-cover" /><figcaption className="text-xs text-slate-500">Ảnh {i+1}</figcaption></figure>)}</div>
      <label className="block text-sm font-medium">Ảnh tham chiếu (1–4 ảnh, tối đa 5 MB/ảnh)<input disabled={sending || disabled} className="mt-1 block w-full rounded-lg border p-2 text-sm" type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={e => { onInvalidate(); void onImages(e.target.files) }} /></label>
      <textarea aria-label="Tin nhắn cho Gemini" maxLength={4000} rows={3} className="w-full rounded-xl border border-slate-300 p-3 text-sm" value={input} disabled={sending || disabled} onChange={e => setInput(e.target.value)} placeholder="Mô tả mong muốn hoặc hỏi Gemini về ảnh…" />
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <p className="text-xs text-slate-500">Bấm Gửi sẽ chuyển nội dung chat và các ảnh hiện tại tới Gemini. Chi phí Gemini theo cấu hình tài khoản; bước này chưa tạo model Meshy. Lịch sử chỉ giữ trong phiên trang này.</p>
      <div className="flex gap-2"><button type="button" className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40" disabled={sending || disabled || reading || !input.trim()} onClick={() => void send()}>Gửi Gemini</button><button type="button" disabled={sending || disabled} className="rounded-lg border px-3 py-2 text-sm" onClick={() => { setMessages([]); setInput(''); setError(''); onInvalidate() }}>Cuộc trò chuyện mới</button></div>
    </div>
  </section>
}
