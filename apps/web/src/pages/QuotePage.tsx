import { useEffect, useState, type FormEvent } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Printer } from 'lucide-react'
import { apiErrorMessage } from '../api/client'
import { acceptPublicQuote, checkoutPublicQuote, getPublicQuote, type PublicQuote } from '../api/quotes'

const vnd = (n: number) => `${Math.round(n).toLocaleString('vi-VN')}đ`
const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('vi-VN') : '')

export function QuotePage() {
  const { token = '' } = useParams()
  const [quote, setQuote] = useState<PublicQuote | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')

  useEffect(() => {
    getPublicQuote(token).then(setQuote).catch((e) => setError(apiErrorMessage(e)))
  }, [token])

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError('')
    try { await fn() } catch (e) { setError(apiErrorMessage(e)) } finally { setBusy(false) }
  }
  const accept = (e: FormEvent) => { e.preventDefault(); void run(async () => setQuote(await acceptPublicQuote(token, { name: name.trim(), phone: phone.trim() }))) }
  const pay = (provider: 'vnpay' | 'momo') => run(async () => { window.location.href = (await checkoutPublicQuote(token, provider)).checkout_url })

  if (!quote) return <div className="quote-page"><div className="quote-card">{error ? <p className="quote-alert" role="alert"><AlertCircle size={16} /> {error}</p> : <p>Đang tải báo giá…</p>}</div></div>

  return (
    <div className="quote-page">
      <article className="quote-card">
        <header className="quote-head">
          <p className="quote-company">{quote.company_name}</p>
          <h1>Báo giá {quote.code}</h1>
          <p className="quote-muted">
            {quote.customer_name ? `Kính gửi ${quote.customer_name} · ` : ''}{quote.pax} khách · {quote.days} ngày{quote.start_date ? ` · khởi hành ${date(quote.start_date)}` : ''}
          </p>
          {quote.status === 'expired'
            ? <p className="quote-alert" role="alert"><AlertCircle size={16} /> Báo giá đã hết hiệu lực. Vui lòng liên hệ {quote.company_name} để được báo giá mới.</p>
            : quote.expires_at && <p className="quote-muted">Có hiệu lực đến {date(quote.expires_at)}</p>}
        </header>

        <section>
          <h2>Lịch trình</h2>
          <ol className="quote-days">
            {quote.itinerary.map((d, i) => <li key={i}><strong>Ngày {i + 1}: {d.title}</strong><span className="quote-muted">{d.stops.join(' · ')}</span></li>)}
          </ol>
        </section>

        {quote.inclusions.length > 0 && (
          <section>
            <h2>Giá đã bao gồm</h2>
            <ul>{quote.inclusions.map((x) => <li key={x}>{x}</li>)}</ul>
          </section>
        )}

        <section className="quote-total">
          <div><span className="quote-muted">Tổng giá trọn gói</span><strong>{vnd(quote.price_vnd)}</strong></div>
          <div><span className="quote-muted">Giá mỗi khách</span><strong>{vnd(quote.price_per_pax)}</strong></div>
          <div><span className="quote-muted">Đặt cọc ({quote.deposit_pct}%)</span><strong>{vnd(quote.deposit_vnd)}</strong></div>
        </section>

        {error && <p className="quote-alert" role="alert"><AlertCircle size={16} /> {error}</p>}

        <div className="quote-actions">
          {quote.can_accept && (
            <form onSubmit={accept} className="quote-form">
              <h2>Chấp nhận báo giá</h2>
              <label>Họ và tên<input required maxLength={180} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
              <label>Số điện thoại<input required type="tel" minLength={6} maxLength={30} pattern="[0-9+\-. ()]+" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" /></label>
              <button className="btn-primary-3d" disabled={busy}>Chấp nhận</button>
            </form>
          )}
          {quote.can_pay && (
            <div className="quote-form">
              <p className="quote-ok"><CheckCircle2 size={16} /> Cảm ơn quý khách đã chấp nhận báo giá. Đặt cọc để giữ chỗ:</p>
              <div className="quote-pay">
                <button className="btn-primary-3d" disabled={busy} onClick={() => void pay('vnpay')}>Đặt cọc {vnd(quote.deposit_vnd)} qua VNPay</button>
                <button className="btn-secondary-3d" disabled={busy} onClick={() => void pay('momo')}>Đặt cọc qua MoMo</button>
              </div>
            </div>
          )}
          {quote.status === 'deposit_paid' && <p className="quote-ok"><CheckCircle2 size={16} /> Đã nhận tiền cọc. {quote.company_name} sẽ liên hệ xác nhận chi tiết chuyến đi.</p>}
          <button className="btn-secondary-3d quote-print" onClick={() => window.print()}><Printer size={16} /> Tải PDF</button>
        </div>
      </article>
    </div>
  )
}

const RESULT: Record<string, [string, string]> = {
  returned: ['Đã ghi nhận thanh toán', 'Hệ thống đang chờ cổng thanh toán xác nhận khoản cọc. Nhà điều hành sẽ liên hệ khi hoàn tất; quý khách không cần thanh toán lại.'],
  failed: ['Thanh toán chưa thành công', 'Giao dịch không hoàn tất và chưa có khoản tiền nào bị thu. Quý khách có thể mở lại liên kết báo giá để thử lại.'],
  invalid: ['Không xác minh được giao dịch', 'Vui lòng liên hệ nhà điều hành nếu quý khách đã bị trừ tiền.'],
}

export function QuoteResultPage() {
  const [params] = useSearchParams()
  const [title, body] = RESULT[params.get('status') ?? ''] ?? RESULT.invalid
  return <div className="quote-page"><div className="quote-card"><h1>{title}</h1><p>{body}</p></div></div>
}
