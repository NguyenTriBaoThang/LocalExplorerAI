export default function ConfirmCard({ text, busy, onYes, onNo }: {
  text: string; busy: boolean; onYes: () => void; onNo: () => void
}) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-stone-200 bg-white p-3 text-sm">
      <p>{text}</p>
      <div className="flex gap-2">
        <button type="button" disabled={busy} onClick={onYes}
          className="rounded bg-emerald-700 px-3 py-1 text-xs text-white disabled:opacity-50">Lập lại</button>
        <button type="button" disabled={busy} onClick={onNo}
          className="rounded border border-stone-300 px-3 py-1 text-xs disabled:opacity-50">Giữ nguyên</button>
      </div>
    </div>
  )
}
