import { useEffect, useState, type FormEvent } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Printer } from 'lucide-react'
import { apiErrorMessage } from '../api/client'
import { acceptPublicQuote, checkoutPublicQuote, getPublicQuote, type PublicQuote } from '../api/quotes'
import { useTranslation } from '../i18n'

export function QuotePage() {
  const { token = '' } = useParams()
  const { t, formatCurrency, formatDate } = useTranslation()
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

  if (!quote) {
    return (
      <div className="quote-page">
        <div className="quote-card">
          {error ? <p className="quote-alert" role="alert"><AlertCircle size={16} /> {error}</p> : <p>{t('common.loading')}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="quote-page">
      <article className="quote-card">
        <header className="quote-head">
          <p className="quote-company">{quote.company_name}</p>
          <h1>{t('quote.title', { code: quote.code })}</h1>
          <p className="quote-muted">
            {quote.customer_name ? t('quote.greeting', { name: quote.customer_name }) : ''}{t('quote.summary', { pax: quote.pax, days: quote.days })}{quote.start_date ? ` · ${formatDate(quote.start_date)}` : ''}
          </p>
          {quote.status === 'expired'
            ? <p className="quote-alert" role="alert"><AlertCircle size={16} /> {t('quote.expired')}</p>
            : quote.expires_at && <p className="quote-muted">{t('quote.validUntil', { date: formatDate(quote.expires_at) })}</p>}
        </header>

        <section>
          <h2>{t('quote.itinerary')}</h2>
          <ol className="quote-days">
            {quote.itinerary.map((d, i) => (
              <li key={i}>
                <strong>{t('quote.dayTitle', { day: i + 1, title: d.title })}</strong>
                <span className="quote-muted">{d.stops.join(' · ')}</span>
              </li>
            ))}
          </ol>
        </section>

        {quote.inclusions.length > 0 && (
          <section>
            <h2>{t('quote.priceIncludes')}</h2>
            <ul>{quote.inclusions.map((x) => <li key={x}>{x}</li>)}</ul>
          </section>
        )}

        <section className="quote-total">
          <div><span className="quote-muted">{t('quote.totalPackage')}</span><strong>{formatCurrency(quote.price_vnd)}</strong></div>
          <div><span className="quote-muted">{t('quote.pricePerPax')}</span><strong>{formatCurrency(quote.price_per_pax)}</strong></div>
          <div><span className="quote-muted">{t('quote.deposit', { pct: quote.deposit_pct })}</span><strong>{formatCurrency(quote.deposit_vnd)}</strong></div>
        </section>

        {error && <p className="quote-alert" role="alert"><AlertCircle size={16} /> {error}</p>}

        <div className="quote-actions">
          {quote.can_accept && (
            <form onSubmit={accept} className="quote-form">
              <h2>{t('quote.acceptTitle')}</h2>
              <label>{t('quote.fullName')}<input required maxLength={180} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
              <label>{t('quote.phone')}<input required type="tel" minLength={6} maxLength={30} pattern="[0-9+\-. ()]+" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" /></label>
              <button className="btn-primary-3d" disabled={busy}>{t('quote.acceptBtn')}</button>
            </form>
          )}
          {quote.can_pay && (
            <div className="quote-form">
              <p className="quote-ok"><CheckCircle2 size={16} /> {t('quote.acceptedNotice')}</p>
              <div className="quote-pay">
                <button className="btn-primary-3d" disabled={busy} onClick={() => void pay('vnpay')}>{t('quote.depositVnPay', { amount: formatCurrency(quote.deposit_vnd) })}</button>
                <button className="btn-secondary-3d" disabled={busy} onClick={() => void pay('momo')}>{t('quote.depositMoMo')}</button>
              </div>
            </div>
          )}
          {quote.status === 'deposit_paid' && <p className="quote-ok"><CheckCircle2 size={16} /> {t('quote.paidNotice')}</p>}
          <button className="btn-secondary-3d quote-print" onClick={() => window.print()}><Printer size={16} /> {t('quote.print')}</button>
        </div>
      </article>
    </div>
  )
}

export function QuoteResultPage() {
  const [params] = useSearchParams()
  const { t } = useTranslation()
  const status = params.get('status') ?? ''

  const resultTitle = status === 'returned'
    ? t('quote.paymentRecorded')
    : status === 'failed'
    ? t('quote.paymentFailed')
    : t('quote.paymentInvalid')

  const resultBody = status === 'returned'
    ? t('quote.paymentPendingDesc')
    : status === 'failed'
    ? t('quote.paymentFailedDesc')
    : t('quote.paymentInvalidDesc')

  return (
    <div className="quote-page">
      <div className="quote-card">
        <h1>{resultTitle}</h1>
        <p>{resultBody}</p>
      </div>
    </div>
  )
}
