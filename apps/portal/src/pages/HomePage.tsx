import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Building2, Check, Lock, ShieldCheck, Store, type LucideIcon } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { ApplicationForm, cleanApplication, EMPTY_APPLICATION } from '../components/ApplicationForm'
import { BrandLogo } from '../components/Brand'
import { UserMenu } from '../components/UserMenu'
import { Alert, Button, cx, Modal, useToast } from '../components/ui'
import { authApi, errorMessage } from '../lib/api'
import type { Role } from '../lib/types'

type PortalWidget = {
  role: Role
  path: string
  title: string
  description: string
  icon: LucideIcon
  accent: string
  features: string[]
}

const WIDGETS: PortalWidget[] = [
  {
    role: 'provider', path: '/partner', title: 'Portal Đối tác', icon: Store,
    description: 'Quản lý hồ sơ cơ sở, trải nghiệm, slot và các yêu cầu đặt chỗ của khách.',
    accent: 'from-brand-500 to-teal-400',
    features: ['Trải nghiệm, slot & lịch theo tuần', 'Đặt chỗ, đánh giá & thống kê doanh thu', 'Địa điểm và hồ sơ đối tác'],
  },
  {
    role: 'admin', path: '/admin', title: 'Portal Quản trị', icon: ShieldCheck,
    description: 'Duyệt hồ sơ đối tác, quản lý người dùng và phân quyền trên toàn hệ thống.',
    accent: 'from-indigo-500 to-brand-500',
    features: ['Thống kê truy cập & hoạt động', 'Đối tác, người dùng & phân quyền', 'Địa điểm, danh thắng & nội dung website'],
  },
]

export function HomePage() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const toast = useToast()
  const [denied, setDenied] = useState<Role | null>((location.state as { denied?: Role } | null)?.denied ?? null)
  const [applyOpen, setApplyOpen] = useState(false)
  const [application, setApplication] = useState(EMPTY_APPLICATION)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { if (location.state) navigate('.', { replace: true, state: null }) }, [location.state, navigate])

  if (!user) return null
  const greetingName = user.display_name || user.email

  const open = (widget: PortalWidget) => {
    if (user.role === widget.role) navigate(widget.path)
    else setDenied(widget.role)
  }

  const apply = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setUser(await authApi.applyAsPartner(cleanApplication(application)))
      setApplyOpen(false)
      toast.success('Đã gửi hồ sơ đối tác. Chúng tôi sẽ phản hồi qua email.')
      navigate('/partner')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50/60 via-white to-slate-50">
      <header className="relative z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
          <BrandLogo />
          <UserMenu />
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-12">
        <section className="relative overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card">
          <img src="/images/skyline.jpg" alt="" className="absolute inset-y-0 right-0 hidden h-full w-[55%] object-cover md:block" />
          <div className="absolute inset-y-0 right-0 hidden w-[55%] bg-gradient-to-r from-white via-white/40 to-transparent md:block" />
          <div className="relative px-6 py-10 sm:px-10 md:max-w-[55%]">
            <p className="text-sm font-medium text-brand-600">Xin chào, {greetingName} 👋</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-ink sm:text-4xl">Bạn muốn vào portal nào?</h1>
            <p className="mt-2 text-slate-500">Chọn khu vực làm việc. Quyền truy cập được kiểm tra theo vai trò tài khoản của bạn.</p>
          </div>
        </section>

        {!user.email_verified_at && (
          <div className="mt-8">
            <Alert tone="amber" title="Email chưa được xác minh"
              action={<Button size="sm" variant="secondary" onClick={() => authApi.resendVerification().then(() => toast.success('Đã gửi lại email xác minh.')).catch((err) => toast.error(errorMessage(err)))}>Gửi lại email</Button>}>
              Kiểm tra hộp thư {user.email} để xác minh tài khoản.
            </Alert>
          </div>
        )}

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {WIDGETS.map((widget) => {
            const allowed = user.role === widget.role
            return (
              <button key={widget.role} type="button" onClick={() => open(widget)}
                className={cx('group relative flex flex-col overflow-hidden rounded-2xl border bg-white p-6 text-left shadow-card transition',
                  allowed ? 'border-slate-200 hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-pop' : 'border-slate-200 hover:border-slate-300')}>
                <div className={cx('absolute inset-x-0 top-0 h-1 bg-gradient-to-r', widget.accent, !allowed && 'opacity-30')} />
                <div className="flex items-start justify-between">
                  <span className={cx('flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm', widget.accent, !allowed && 'opacity-40 grayscale')}>
                    <widget.icon className="h-6 w-6" />
                  </span>
                  {allowed
                    ? <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"><Check className="h-3.5 w-3.5" /> Có quyền truy cập</span>
                    : <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500"><Lock className="h-3.5 w-3.5" /> Không có quyền</span>}
                </div>
                <h2 className="mt-5 text-lg font-semibold text-slate-900">{widget.title}</h2>
                <p className="mt-1.5 text-sm text-slate-500">{widget.description}</p>
                <ul className="mt-5 space-y-2">
                  {widget.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm text-slate-600">
                      <span className="h-1.5 w-1.5 rounded-full bg-slate-300" /> {feature}
                    </li>
                  ))}
                </ul>
                <span className={cx('mt-6 inline-flex items-center gap-1.5 text-sm font-semibold', allowed ? 'text-brand-600' : 'text-slate-400')}>
                  {allowed ? 'Vào portal' : 'Xem chi tiết'}
                  <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                </span>
              </button>
            )
          })}
        </div>
      </main>

      <Modal open={denied !== null} onClose={() => setDenied(null)} size="sm"
        title={denied === 'provider' && user.role === 'traveler' ? 'Bạn chưa là đối tác' : 'Không có quyền truy cập'}
        footer={denied === 'provider' && user.role === 'traveler'
          ? <><Button variant="secondary" onClick={() => setDenied(null)}>Để sau</Button><Button icon={Building2} onClick={() => { setDenied(null); setApplyOpen(true) }}>Đăng ký làm đối tác</Button></>
          : <Button variant="secondary" onClick={() => setDenied(null)}>Đã hiểu</Button>}>
        <div className="flex gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-600"><Lock className="h-5 w-5" /></span>
          <p className="text-sm text-slate-600">
            {denied === 'provider'
              ? user.role === 'traveler'
                ? 'Tài khoản của bạn chưa được liên kết với hồ sơ đối tác. Gửi hồ sơ đăng ký để bắt đầu đưa trải nghiệm của bạn lên Local Explorer.'
                : 'Portal Đối tác chỉ dành cho tài khoản đối tác. Tài khoản quản trị dùng Portal Quản trị.'
              : 'Portal Quản trị chỉ dành cho quản trị viên. Liên hệ quản trị viên hệ thống nếu bạn cần quyền này.'}
          </p>
        </div>
      </Modal>

      <Modal open={applyOpen} onClose={() => setApplyOpen(false)} size="lg" title="Đăng ký làm đối tác" description="Hồ sơ sẽ được đội ngũ Local Explorer duyệt trong 1–2 ngày làm việc."
        footer={<><Button variant="secondary" onClick={() => setApplyOpen(false)}>Hủy</Button><Button type="submit" form="apply-form" loading={busy}>Gửi hồ sơ</Button></>}>
        <form id="apply-form" onSubmit={apply} className="space-y-5">
          {error && <Alert tone="red">{error}</Alert>}
          <ApplicationForm value={application} onChange={setApplication} />
        </form>
      </Modal>
    </div>
  )
}
