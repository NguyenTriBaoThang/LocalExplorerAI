import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, LayoutGrid, LogOut } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { ROLES } from '../lib/format'
import { Avatar } from './ui'

export function UserMenu() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const close = (event: MouseEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  if (!user) return null
  const name = user.display_name || user.email
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((value) => !value)} aria-haspopup="menu" aria-expanded={open} className="flex items-center gap-2.5 rounded-lg py-1 pl-1 pr-2 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-100">
        <Avatar name={name} size="sm" />
        <span className="hidden text-left leading-tight sm:block">
          <span className="block max-w-[160px] truncate text-sm font-medium text-slate-900">{name}</span>
          <span className="block text-xs text-slate-500">{ROLES[user.role]}</span>
        </span>
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>
      {open && (
        <div className="animate-pop-in absolute right-0 z-40 mt-2 w-60 rounded-xl border border-slate-200 bg-white p-1.5 shadow-pop">
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium text-slate-900">{name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <div className="my-1 h-px bg-slate-100" />
          <button type="button" onClick={() => { setOpen(false); navigate('/') }} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
            <LayoutGrid className="h-4 w-4 text-slate-400" /> Chọn portal
          </button>
          <button type="button" onClick={async () => { await signOut(); navigate('/login') }} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-rose-600 hover:bg-rose-50">
            <LogOut className="h-4 w-4" /> Đăng xuất
          </button>
        </div>
      )}
    </div>
  )
}
