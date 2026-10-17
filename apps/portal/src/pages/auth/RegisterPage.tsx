import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import { ApplicationForm, cleanApplication, EMPTY_APPLICATION } from '../../components/ApplicationForm'
import { AuthLayout } from '../../components/AuthLayout'
import { Alert, Button, cx, DescriptionList, Field, Input } from '../../components/ui'
import { authApi, errorMessage } from '../../lib/api'
import { BUSINESS_TYPES } from '../../lib/format'

const STEPS = ['Tài khoản', 'Cơ sở kinh doanh', 'Pháp lý', 'Xác nhận']

export function RegisterPage() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [account, setAccount] = useState({ display_name: '', email: '', password: '', confirm: '' })
  const [application, setApplication] = useState(EMPTY_APPLICATION)
  const [agreed, setAgreed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const passwordMismatch = account.confirm.length > 0 && account.password !== account.confirm

  const next = (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (step === 0 && account.password !== account.confirm) return setError('Mật khẩu nhập lại không khớp.')
    if (step < STEPS.length - 1) return setStep(step + 1)
    void submit()
  }

  const submit = async () => {
    setBusy(true)
    try {
      const user = await authApi.registerPartner({
        email: account.email, display_name: account.display_name, password: account.password, application: cleanApplication(application),
      })
      setUser(user)
      navigate('/partner', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout wide title="Đăng ký đối tác" subtitle={<>Đã có tài khoản? <Link to="/login" className="font-medium text-brand-600 hover:text-brand-700">Đăng nhập</Link></>}>
      <ol className="mb-8 flex items-center gap-2">
        {STEPS.map((label, index) => (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span className={cx('flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition',
              index < step ? 'bg-brand-600 text-white' : index === step ? 'bg-brand-50 text-brand-700 ring-2 ring-brand-600' : 'bg-slate-100 text-slate-500')}>
              {index < step ? <Check className="h-3.5 w-3.5" /> : index + 1}
            </span>
            <span className={cx('hidden text-xs font-medium sm:block', index === step ? 'text-slate-900' : 'text-slate-500')}>{label}</span>
            {index < STEPS.length - 1 && <span className={cx('h-px flex-1', index < step ? 'bg-brand-600' : 'bg-slate-200')} />}
          </li>
        ))}
      </ol>

      <form onSubmit={next} className="space-y-5">
        {error && <Alert tone="red">{error}</Alert>}

        {step === 0 && (
          <>
            <Field label="Họ tên người đại diện" required>
              <Input value={account.display_name} onChange={(e) => setAccount({ ...account, display_name: e.target.value })} required autoFocus />
            </Field>
            <Field label="Email đăng nhập" required hint="Chúng tôi sẽ gửi email xác minh và kết quả duyệt hồ sơ tới địa chỉ này.">
              <Input type="email" autoComplete="email" value={account.email} onChange={(e) => setAccount({ ...account, email: e.target.value })} required />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Mật khẩu" required hint="Tối thiểu 12 ký tự.">
                <Input type="password" autoComplete="new-password" minLength={12} value={account.password} onChange={(e) => setAccount({ ...account, password: e.target.value })} required />
              </Field>
              <Field label="Nhập lại mật khẩu" required error={passwordMismatch ? 'Mật khẩu không khớp' : undefined}>
                <Input type="password" autoComplete="new-password" invalid={passwordMismatch} value={account.confirm} onChange={(e) => setAccount({ ...account, confirm: e.target.value })} required />
              </Field>
            </div>
          </>
        )}
        {step === 1 && <ApplicationForm section="business" value={application} onChange={setApplication} />}
        {step === 2 && <ApplicationForm section="legal" value={application} onChange={setApplication} />}
        {step === 3 && (
          <div className="space-y-5">
            <div className="rounded-xl border border-slate-200 px-5 py-2">
              <DescriptionList items={[
                ['Người đại diện', account.display_name],
                ['Email', account.email],
                ['Cơ sở', application.business_name],
                ['Loại hình', BUSINESS_TYPES[application.business_type]],
                ['Điện thoại', application.contact_phone],
                ['Địa chỉ', application.address],
                ['Mã số thuế', application.tax_code],
                ['Giấy tờ', application.document_urls.filter(Boolean).length ? `${application.document_urls.filter(Boolean).length} liên kết` : ''],
              ]} />
            </div>
            <label className="flex items-start gap-3 text-sm text-slate-600">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" required />
              Tôi xác nhận thông tin trên là chính xác và đồng ý với điều khoản hợp tác của Local Explorer.
            </label>
            <Alert tone="brand">Sau khi gửi, bạn có thể đăng nhập ngay. Hồ sơ sẽ được duyệt trong 1–2 ngày làm việc; bạn chỉ mở được slot sau khi hồ sơ được duyệt.</Alert>
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          {step > 0
            ? <Button type="button" variant="ghost" icon={ArrowLeft} onClick={() => setStep(step - 1)}>Quay lại</Button>
            : <span />}
          <Button type="submit" size="lg" loading={busy} disabled={passwordMismatch || (step === 3 && !agreed)}>
            {step === STEPS.length - 1 ? 'Gửi hồ sơ' : <>Tiếp tục <ArrowRight className="h-4 w-4" /></>}
          </Button>
        </div>
      </form>
    </AuthLayout>
  )
}
