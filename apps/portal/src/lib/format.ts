const dateTime = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' })
const dateOnly = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' })
const money = new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 })
const relative = new Intl.RelativeTimeFormat('vi', { numeric: 'auto' })

export const formatDateTime = (value: string | null | undefined) => (value ? dateTime.format(new Date(value)) : '—')
export const formatDate = (value: string | null | undefined) => (value ? dateOnly.format(new Date(value)) : '—')
export const formatMoney = (value: number) => money.format(value)

export function timeAgo(value: string | null | undefined): string {
  if (!value) return '—'
  const seconds = (new Date(value).getTime() - Date.now()) / 1000
  const steps: Array<[number, Intl.RelativeTimeFormatUnit]> = [[60, 'second'], [60, 'minute'], [24, 'hour'], [30, 'day'], [12, 'month']]
  let amount = seconds
  for (const [size, unit] of steps) {
    if (Math.abs(amount) < size) return relative.format(Math.round(amount), unit)
    amount /= size
  }
  return relative.format(Math.round(amount), 'year')
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  return (parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/** `<input type="datetime-local">` value -> ISO string with the browser's offset (the API requires a timezone). */
export function localInputToIso(value: string): string {
  const date = new Date(value)
  const offset = -date.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, '0')
  return `${value.length === 16 ? `${value}:00` : value}${sign}${pad(offset / 60)}:${pad(offset % 60)}`
}

export function isoToLocalInput(value: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`
}

export const BUSINESS_TYPES: Record<string, string> = {
  household: 'Hộ kinh doanh',
  company: 'Công ty',
  cooperative: 'Hợp tác xã',
  individual: 'Cá nhân',
  other: 'Khác',
}

export const INTENTS: Record<string, string> = {
  'thủ_công': 'Thủ công',
  'ẩm_thực': 'Ẩm thực',
  'văn_hóa': 'Văn hóa',
  'thư_giãn': 'Thư giãn',
}

export const ROLES: Record<string, string> = { traveler: 'Du khách', provider: 'Đối tác', admin: 'Quản trị viên' }
