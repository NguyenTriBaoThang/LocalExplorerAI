import type { ReactNode } from 'react'
import { CalendarClock, MapPinned, ShieldCheck } from 'lucide-react'
import { BrandLogo } from './Brand'

const HIGHLIGHTS = [
  { icon: CalendarClock, title: 'Slot theo thời gian thực', text: 'Mở ca, cập nhật số chỗ và nhận yêu cầu đặt chỗ ngay khi khách lên lịch trình.' },
  { icon: MapPinned, title: 'Hiện diện trên bản đồ 3D', text: 'Địa điểm và trải nghiệm của bạn xuất hiện trong lịch trình AI gợi ý cho du khách.' },
  { icon: ShieldCheck, title: 'Đối tác được xác minh', text: 'Hồ sơ được duyệt trước khi hiển thị, giúp du khách yên tâm đặt chỗ.' },
]

export function AuthLayout({ title, subtitle, children, wide }: { title: string; subtitle?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <section className="relative hidden overflow-hidden bg-sky-50 lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -left-24 top-24 h-80 w-80 rounded-full bg-sky-200/40 blur-3xl" />
        <div className="pointer-events-none absolute -right-20 bottom-40 h-72 w-72 rounded-full bg-teal-200/40 blur-3xl" />
        <div className="relative px-12 pt-10"><BrandLogo subtitle="Portal đối tác & quản trị" /></div>
        <div className="relative px-12 pt-10 xl:pt-14">
          <h2 className="max-w-lg text-[32px] font-bold leading-tight tracking-tight text-ink">
            Đưa trải nghiệm địa phương đến <span className="bg-gradient-to-r from-brand-600 to-teal-500 bg-clip-text text-transparent">đúng du khách</span>.
          </h2>
          <ul className="mt-8 grid max-w-lg gap-4">
            {HIGHLIGHTS.map((item) => (
              <li key={item.title} className="flex gap-3.5">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-brand-600 shadow-card ring-1 ring-slate-200/70"><item.icon className="h-5 w-5" /></span>
                <div>
                  <p className="text-sm font-semibold text-ink">{item.title}</p>
                  <p className="mt-0.5 text-sm text-slate-500">{item.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        {/* Full-bleed skyline that fades into the panel, so it fills the column at any height. */}
        <div className="relative mt-auto h-[46vh] min-h-[260px] w-full">
          <img src="/images/skyline.jpg" alt="Toàn cảnh TP. Hồ Chí Minh" className="absolute inset-0 h-full w-full object-cover object-[center_60%]" />
          <div className="absolute inset-x-0 top-0 h-2/5 bg-gradient-to-b from-sky-50 via-sky-50/70 to-transparent" />
          <p className="absolute bottom-4 left-12 rounded-full bg-white/80 px-3 py-1 text-xs text-slate-600 backdrop-blur">© {new Date().getFullYear()} Local Explorer AI · TP. Hồ Chí Minh</p>
        </div>
      </section>
      <section className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className={wide ? 'w-full max-w-xl' : 'w-full max-w-sm'}>
          <div className="mb-8 lg:hidden"><BrandLogo /></div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </section>
    </div>
  )
}
