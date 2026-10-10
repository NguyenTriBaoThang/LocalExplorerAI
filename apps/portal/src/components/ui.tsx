import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, Info, Loader2, X, type LucideIcon } from 'lucide-react'
import { initials } from '../lib/format'

export function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

/* ---------- Buttons ---------- */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: LucideIcon
}

const BUTTON_VARIANTS = {
  primary: 'bg-brand-600 text-white shadow-sm hover:bg-brand-700 focus-visible:ring-brand-200',
  secondary: 'bg-white text-slate-700 border border-slate-300 shadow-sm hover:bg-slate-50 focus-visible:ring-slate-200',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-slate-200',
  danger: 'bg-rose-600 text-white shadow-sm hover:bg-rose-700 focus-visible:ring-rose-200',
  success: 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 focus-visible:ring-emerald-200',
}
const BUTTON_SIZES = { sm: 'h-8 px-3 text-xs gap-1.5', md: 'h-9 px-3.5 text-sm gap-2', lg: 'h-11 px-5 text-sm gap-2' }

export function Button({ variant = 'primary', size = 'md', loading, icon: Icon, className, children, disabled, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center rounded-lg font-medium transition focus:outline-none focus-visible:ring-4 disabled:cursor-not-allowed disabled:opacity-60',
        BUTTON_VARIANTS[variant], BUTTON_SIZES[size], className,
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  )
}

export function IconButton({ icon: Icon, label, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: LucideIcon; label: string }) {
  return (
    <button {...props} aria-label={label} title={label}
      className={cx('inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900', className)}>
      <Icon className="h-4 w-4" />
    </button>
  )
}

/* ---------- Form controls ---------- */

export function Field({ label, hint, error, required, children, className }: { label: string; hint?: string; error?: string; required?: boolean; children: ReactNode; className?: string }) {
  return (
    <label className={cx('block', className)}>
      <span className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}{required && <span className="ml-0.5 text-rose-500">*</span>}
      </span>
      {children}
      {error ? <span className="mt-1 block text-xs text-rose-600">{error}</span> : hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
    </label>
  )
}

export function Input({ className, invalid, ...props }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return <input {...props} className={cx('input', invalid && 'input-error', className)} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx('input min-h-[96px] resize-y', className)} />
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx('input pr-8', className)}>{children}</select>
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (value: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="inline-flex items-center gap-2.5 text-sm text-slate-700">
      <span className={cx('relative h-5 w-9 rounded-full transition', checked ? 'bg-brand-600' : 'bg-slate-300')}>
        <span className={cx('absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition', checked ? 'left-[18px]' : 'left-0.5')} />
      </span>
      {label}
    </button>
  )
}

/* ---------- Surfaces ---------- */

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx('min-w-0 rounded-xl border border-slate-200 bg-white shadow-card', className)}>{children}</div>
}

export function CardHeader({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function StatCard({ label, value, icon: Icon, tone = 'brand', hint }: { label: string; value: ReactNode; icon: LucideIcon; tone?: Tone; hint?: ReactNode }) {
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-slate-500 sm:text-sm">{label}</p>
        <span className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg sm:h-9 sm:w-9', TONE_SOFT[tone])}><Icon className="h-4 w-4 sm:h-[18px] sm:w-[18px]" /></span>
      </div>
      <p className="mt-2 truncate text-2xl font-semibold tracking-tight text-slate-900 sm:mt-3 sm:text-3xl">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </Card>
  )
}

/* ---------- Badges & status ---------- */

type Tone = 'brand' | 'gray' | 'green' | 'amber' | 'red' | 'violet'
const TONE_SOFT: Record<Tone, string> = {
  brand: 'bg-brand-50 text-brand-700',
  gray: 'bg-slate-100 text-slate-600',
  green: 'bg-emerald-50 text-emerald-700',
  amber: 'bg-amber-50 text-amber-700',
  red: 'bg-rose-50 text-rose-700',
  violet: 'bg-violet-50 text-violet-700',
}
const TONE_DOT: Record<Tone, string> = {
  brand: 'bg-brand-500', gray: 'bg-slate-400', green: 'bg-emerald-500', amber: 'bg-amber-500', red: 'bg-rose-500', violet: 'bg-violet-500',
}

export function Badge({ tone = 'gray', dot, children }: { tone?: Tone; dot?: boolean; children: ReactNode }) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-black/5', TONE_SOFT[tone])}>
      {dot && <span className={cx('h-1.5 w-1.5 rounded-full', TONE_DOT[tone])} />}
      {children}
    </span>
  )
}

const STATUS: Record<string, [string, Tone]> = {
  // partner profile
  pending: ['Chờ duyệt', 'amber'], verified: ['Đã duyệt', 'green'], rejected: ['Từ chối', 'red'], suspended: ['Tạm khóa', 'red'],
  mock: ['Demo', 'gray'], simulated: ['Demo', 'gray'], hidden: ['Đã ẩn', 'gray'], draft: ['Nháp', 'gray'], published: ['Đã đăng', 'green'],
  // slots
  open: ['Còn chỗ', 'green'], available: ['Còn chỗ', 'green'], full: ['Hết chỗ', 'amber'], cancelled: ['Đã hủy', 'gray'],
  tentative: ['Tạm tính', 'violet'], unavailable: ['Không khả dụng', 'gray'],
  // bookings
  pending_provider: ['Chờ xác nhận', 'amber'], awaiting_payment: ['Chờ thanh toán', 'brand'], confirmed: ['Đã xác nhận', 'green'],
  cancellation_requested: ['Yêu cầu hủy', 'amber'], expired: ['Hết hạn', 'gray'], completed: ['Hoàn tất', 'green'],
  // users
  active: ['Hoạt động', 'green'], inactive: ['Đã khóa', 'red'],
}

export function StatusBadge({ status }: { status: string }) {
  const [label, tone] = STATUS[status] ?? [status, 'gray' as Tone]
  return <Badge tone={tone} dot>{label}</Badge>
}

export function Avatar({ name, size = 'md' }: { name: string; size?: 'sm' | 'md' | 'lg' }) {
  const palette = ['bg-brand-100 text-brand-700', 'bg-emerald-100 text-emerald-700', 'bg-amber-100 text-amber-700', 'bg-violet-100 text-violet-700', 'bg-rose-100 text-rose-700']
  const color = palette[[...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % palette.length]
  const dimension = { sm: 'h-7 w-7 text-[11px]', md: 'h-9 w-9 text-xs', lg: 'h-12 w-12 text-sm' }[size]
  return <span className={cx('inline-flex shrink-0 items-center justify-center rounded-full font-semibold', color, dimension)}>{initials(name)}</span>
}

/* ---------- Feedback ---------- */

export function Alert({ tone = 'brand', title, children, action }: { tone?: 'brand' | 'green' | 'amber' | 'red'; title?: ReactNode; children?: ReactNode; action?: ReactNode }) {
  const Icon = tone === 'green' ? CheckCircle2 : tone === 'brand' ? Info : AlertCircle
  const styles = {
    brand: 'border-brand-200 bg-brand-50 text-brand-900', green: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    amber: 'border-amber-200 bg-amber-50 text-amber-900', red: 'border-rose-200 bg-rose-50 text-rose-900',
  }[tone]
  return (
    <div className={cx('flex gap-3 rounded-xl border p-4 text-sm', styles)}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0 opacity-80" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cx(title ? 'mt-1' : '', 'opacity-90')}>{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  )
}

export function Spinner({ label = 'Đang tải…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Loader2 className="h-5 w-5 animate-spin text-brand-600" /> {label}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500"><Icon className="h-6 w-6" /></span>
      <p className="mt-4 text-sm font-semibold text-slate-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/* ---------- Overlays ---------- */

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])
}

export function Modal({ open, onClose, title, description, children, footer, size = 'md' }: {
  open: boolean; onClose: () => void; title: string; description?: string; children: ReactNode; footer?: ReactNode; size?: 'sm' | 'md' | 'lg'
}) {
  useEscape(open, onClose)
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
      <div className="animate-fade-in absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]" onClick={onClose} />
      <div role="dialog" aria-modal="true" className={cx('animate-pop-in relative flex max-h-[90vh] w-full flex-col rounded-2xl bg-white shadow-pop', { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl' }[size])}>
        <div className="flex items-start justify-between gap-4 px-6 pt-5">
          <div>
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
          </div>
          <IconButton icon={X} label="Đóng" onClick={onClose} className="-mr-2 -mt-1" />
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 rounded-b-2xl border-t border-slate-100 bg-slate-50/70 px-6 py-3.5">{footer}</div>}
      </div>
    </div>
  )
}

export function Drawer({ open, onClose, title, subtitle, children, footer }: {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode
}) {
  useEscape(open, onClose)
  if (!open) return null
  return (
    <div className="fixed inset-0 z-40">
      <div className="animate-fade-in absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <aside className="animate-slide-in absolute inset-y-0 right-0 flex w-full max-w-xl flex-col bg-white shadow-pop">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div className="min-w-0">
            <div className="truncate text-base font-semibold text-slate-900">{title}</div>
            {subtitle && <div className="mt-0.5 text-sm text-slate-500">{subtitle}</div>}
          </div>
          <IconButton icon={X} label="Đóng" onClick={onClose} />
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 bg-slate-50/70 px-6 py-3.5">{footer}</div>}
      </aside>
    </div>
  )
}

/* ---------- Navigation helpers ---------- */

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (value: T) => void; items: Array<{ value: T; label: string; count?: number }> }) {
  return (
    <div className="no-scrollbar inline-flex max-w-full overflow-x-auto rounded-lg bg-slate-100 p-1">
      {items.map((item) => (
        <button key={item.value} type="button" onClick={() => onChange(item.value)}
          className={cx('inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition',
            value === item.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800')}>
          {item.label}
          {item.count !== undefined && (
            <span className={cx('rounded-full px-1.5 text-xs', value === item.value ? 'bg-brand-50 text-brand-700' : 'bg-slate-200 text-slate-600')}>{item.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

export function Pagination({ offset, limit, total, onChange }: { offset: number; limit: number; total: number; onChange: (offset: number) => void }) {
  if (total <= limit) return null
  const from = offset + 1
  const to = Math.min(offset + limit, total)
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm text-slate-500">
      <span>{from}–{to} / {total}</span>
      <div className="flex gap-1">
        <IconButton icon={ChevronLeft} label="Trang trước" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))} className="disabled:opacity-40" />
        <IconButton icon={ChevronRight} label="Trang sau" disabled={to >= total} onClick={() => onChange(offset + limit)} className="disabled:opacity-40" />
      </div>
    </div>
  )
}

export function DescriptionList({ items }: { items: Array<[string, ReactNode]> }) {
  return (
    <dl className="divide-y divide-slate-100">
      {items.map(([term, detail]) => (
        <div key={term} className="grid grid-cols-3 gap-4 py-2.5 text-sm">
          <dt className="text-slate-500">{term}</dt>
          <dd className="col-span-2 break-words text-slate-900">{detail || <span className="text-slate-400">—</span>}</dd>
        </div>
      ))}
    </dl>
  )
}

/* ---------- Toasts ---------- */

type Toast = { id: number; tone: 'success' | 'error' | 'info'; message: string }
const ToastContext = createContext<(tone: Toast['tone'], message: string) => void>(() => undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((tone: Toast['tone'], message: string) => {
    const id = Date.now() + Math.random()
    setToasts((items) => [...items, { id, tone, message }])
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 4000)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2">
        {toasts.map((toast) => (
          <div key={toast.id} className="animate-pop-in pointer-events-auto flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-pop">
            {toast.tone === 'success'
              ? <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
              : toast.tone === 'info'
                ? <Info className="h-5 w-5 shrink-0 text-brand-600" />
                : <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />}
            <p className="text-slate-700">{toast.message}</p>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const push = useContext(ToastContext)
  return { success: (message: string) => push('success', message), error: (message: string) => push('error', message), info: (message: string) => push('info', message) }
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</h4>
      {action}
    </div>
  )
}
