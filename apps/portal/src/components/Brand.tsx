export function BrandMark({ className = 'h-9 w-9' }: { className?: string }) {
  return <img src="/logo-mark.png" alt="" className={`${className} object-contain`} />
}

export function BrandLogo({ subtitle = 'Portal' }: { subtitle?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark />
      <div className="leading-tight">
        <p className="text-sm font-bold text-ink">Local Explorer <span className="text-teal-500">AI</span></p>
        <p className="text-xs text-slate-500">{subtitle}</p>
      </div>
    </div>
  )
}
